// EditMode 테스트: 소유감 실험 기록 형식(설계 2.4 — 분석 스크립트와의 계약), 문구 파일, 기록용 기하 계산.
// UnityEngine 없이 돈다(dotnet compile-check에서도 실행). 기록은 임시 폴더에 쓰고 지운다.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using IFS.SceneSpec.Ownership;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class OwnershipRecordTests
    {
        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-ownership-record-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        // 계약 문자열을 여기 그대로 적어 둔다(상수를 바꾸면 이 테스트가 깨져야 한다).
        const string Headpose = "time_ms,phase,position,variant,head_x,head_y,head_z,head_qx,head_qy,head_qz,head_qw,obj_x,obj_y,obj_z,distance_m,angle_deg";
        const string Ratings = "position,variant,rating,rt_ms,view_ms,cancelled,item";
        const string Difference = "variant,rating,rt_ms";
        const string Events = "time_ms,event,detail";

        static void AssertUtf8NoBomLf(string path)
        {
            var bytes = File.ReadAllBytes(path);
            Assert.That(bytes.Length >= 3 && bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF, Is.False, Path.GetFileName(path) + " BOM 없음");
            Assert.That(bytes.Contains((byte)'\r'), Is.False, Path.GetFileName(path) + " 줄바꿈 \\n");
        }

        [Test]
        public void Record_files_have_contract_headers_layout_and_encoding()
        {
            Assert.That(OwnershipRecordWriter.HeadposeHeader, Is.EqualTo(Headpose));
            Assert.That(OwnershipRecordWriter.RatingsHeader, Is.EqualTo(Ratings));
            Assert.That(OwnershipRecordWriter.DifferenceHeader, Is.EqualTo(Difference));
            Assert.That(OwnershipRecordWriter.EventsHeader, Is.EqualTo(Events));

            var started = new DateTime(2026, 11, 17, 1, 2, 3, DateTimeKind.Utc);
            string dir;
            using (var w = new OwnershipRecordWriter(_tmp, 7, "SYN/sess", started))
            {
                dir = w.Directory;
                w.Head(new HeadSample { TimeMs = 50, Phase = "viewing", Position = 1, Variant = "size", HeadX = 0, HeadY = 1.6, HeadZ = 0, Qw = 1,
                    HasObject = true, ObjX = 0, ObjY = 1.28, ObjZ = 1.19, DistanceM = 1.23, AngleDeg = 15.5 });
                w.Head(new HeadSample { TimeMs = 100, Phase = "rating", Position = 1, HeadY = 1.6, Qw = 1 });
                w.Rating(1, "size", 7, 812, 30000, true, "resemblance");
                w.Rating(1, "size", 5, 400, 30000, false, "resemblance");
                w.Difference("color", 4, 1234);
                w.Event(0, "phase", "viewing;position=1;variant=size");
                w.Event(5, "note", "쉼표, 따옴표\" 포함");
                w.WriteSummary(OwnershipRecordWriter.BuildSummary(true, null, 3, "orig", 900,
                    new Dictionary<string, int> { { "size_hi", 2 }, { "color_lo", 3 }, { "size", 5 }, { "orig", 6 } }, started.AddMinutes(5)));
                w.WriteManifest(new JObject { ["recordVersion"] = OwnershipManifest.RecordVersion });
            }
            Assert.That(dir, Is.EqualTo(Path.Combine(_tmp, "ownership", "P007", "SYN_sess", "20261117-010203")), "폴더 = ownership/P{번호:000}/{sessionId}/{UTC}");
            foreach (var f in new[] { "manifest.json", "headpose.csv", "ratings.csv", "difference.csv", "events.csv", "summary.json" })
            {
                Assert.That(File.Exists(Path.Combine(dir, f)), Is.True, f);
                AssertUtf8NoBomLf(Path.Combine(dir, f));
            }
            var head = File.ReadAllLines(Path.Combine(dir, "headpose.csv"));
            Assert.That(head[0], Is.EqualTo(Headpose));
            Assert.That(head[1], Is.EqualTo("50,viewing,1,size,0.0000,1.6000,0.0000,0.000000,0.000000,0.000000,1.000000,0.0000,1.2800,1.1900,1.2300,15.50"));
            Assert.That(head[2], Is.EqualTo("100,rating,1,,0.0000,1.6000,0.0000,0.000000,0.000000,0.000000,1.000000,,,,,"), "형상 없으면 빈칸");
            Assert.That(head[1].Split(',').Length, Is.EqualTo(Headpose.Split(',').Length));
            var ratings = File.ReadAllLines(Path.Combine(dir, "ratings.csv"));
            Assert.That(ratings, Is.EqualTo(new[] { Ratings, "1,size,7,812,30000,1,resemblance", "1,size,5,400,30000,0,resemblance" }));
            Assert.That(File.ReadAllLines(Path.Combine(dir, "difference.csv")), Is.EqualTo(new[] { Difference, "color,4,1234" }));
            var events = File.ReadAllLines(Path.Combine(dir, "events.csv"));
            Assert.That(events[0], Is.EqualTo(Events));
            Assert.That(events[2], Is.EqualTo("5,note,\"쉼표, 따옴표\"\" 포함\""));
            var summary = OwnershipVariantTests.ParseNoDates(File.ReadAllText(Path.Combine(dir, "summary.json")));
            Assert.That(summary.Properties().Select(p => p.Name), Is.EqualTo(new[] { "completed", "abortedAt", "finalChoice", "ratings", "endedAtUtc" }));
            Assert.That((bool)summary["completed"], Is.True);
            Assert.That(summary["abortedAt"].Type, Is.EqualTo(JTokenType.Null));
            Assert.That((int)summary["finalChoice"]["position"], Is.EqualTo(3));
            Assert.That((string)summary["finalChoice"]["variant"], Is.EqualTo("orig"));
            Assert.That((long)summary["finalChoice"]["rt_ms"], Is.EqualTo(900));
            Assert.That(((JObject)summary["ratings"]).Properties().Select(p => p.Name), Is.EqualTo(new[] { "orig", "size", "color_lo", "size_hi" }), "조건 순서");
            Assert.That((string)summary["endedAtUtc"], Is.EqualTo("2026-11-17T01:07:03.000Z"));
        }

        [Test]
        public void Restarting_in_the_same_second_does_not_overwrite()
        {
            var t = new DateTime(2026, 11, 17, 1, 2, 3, DateTimeKind.Utc);
            string a, b;
            using (var w = new OwnershipRecordWriter(_tmp, 1, "S", t)) a = w.Directory;
            using (var w = new OwnershipRecordWriter(_tmp, 1, "S", t)) b = w.Directory;
            Assert.That(b, Is.Not.EqualTo(a));
            Assert.That(b, Is.EqualTo(a + "-2"));
        }

        [Test]
        public void Aborted_summary_records_phase_and_no_choice()
        {
            var s = OwnershipRecordWriter.BuildSummary(false, "rating", null, null, null, new Dictionary<string, int> { { "form", 2 } }, DateTime.UtcNow);
            Assert.That((bool)s["completed"], Is.False);
            Assert.That((string)s["abortedAt"], Is.EqualTo("rating"));
            Assert.That(s["finalChoice"].Type, Is.EqualTo(JTokenType.Null));
            Assert.That((int)s["ratings"]["form"], Is.EqualTo(2));
        }

        // ── 표본 시각·제시 시작 이벤트 ─────────────────────────────────────
        [Test]
        public void Head_sample_clock_writes_at_most_one_sample_per_frame_at_the_real_time()
        {
            var clock = new HeadSampleClock(20);
            Assert.That(clock.IntervalSeconds, Is.EqualTo(0.05).Within(1e-12));
            var taken = new List<double>();
            double t = 0;
            void Frame(double dt)
            {
                t += dt;
                int before = taken.Count;
                if (clock.TryTake(t)) taken.Add(t);
                Assert.That(taken.Count - before, Is.LessThanOrEqualTo(1));
            }
            clock.Reset();
            Frame(0);                                   // 단계 시작 직후 첫 프레임은 바로 쓴다
            for (int i = 0; i < 6; i++) Frame(0.02);    // 0.02 … 0.12: 0.05 이상 지난 0.06, 0.12에서만
            Frame(1.0);                                 // 1초 밀린 프레임 하나 → 표본 하나(1.12), 과거 시각으로 채우지 않음
            for (int i = 0; i < 3; i++) Frame(0.02);    // 1.14 1.16 1.18 → 1.18
            Assert.That(taken, Is.EqualTo(new[] { 0.0, 0.06, 0.12, 1.12, 1.18 }).Within(1e-9));
            Assert.That(clock.TryTake(1.18), Is.False, "같은 시각(같은 프레임)에 두 번 쓰지 않는다");
            clock.Reset();
            Assert.That(clock.TryTake(1.19), Is.True, "단계가 바뀌면 다음 프레임에 바로");
            Assert.Throws<ArgumentOutOfRangeException>(() => new HeadSampleClock(0));
        }

        [Test]
        public void Viewing_start_event_has_a_fixed_machine_readable_detail()
        {
            Assert.That(OwnershipRecordWriter.ViewingStartEvent, Is.EqualTo("viewing_start"));
            Assert.That(OwnershipRecordWriter.ViewingStartDetail(2, "form"), Is.EqualTo("position=2;variant=form"));
            using (var w = new OwnershipRecordWriter(_tmp, 1, "S", new DateTime(2026, 11, 17, 1, 2, 3, DateTimeKind.Utc)))
            {
                w.Event(1234, OwnershipRecordWriter.ViewingStartEvent, OwnershipRecordWriter.ViewingStartDetail(5, "orig"));
                w.Dispose();
                var lines = File.ReadAllLines(Path.Combine(w.Directory, OwnershipRecordWriter.EventsFile));
                Assert.That(lines[1], Is.EqualTo("1234,viewing_start,position=5;variant=orig"), "따옴표 없이 한 칸");
            }
        }

        // ── 문구 ─────────────────────────────────────────────────────────
        [Test]
        public void Task_text_file_has_all_draft_texts_without_clinical_words()
        {
            string path = Path.Combine(Application.streamingAssetsPath, OwnershipTaskText.DefaultRelativePath);
            var t = OwnershipTaskText.Load(path);
            Assert.That(t.Version, Is.EqualTo("0.2"));
            Assert.That(t.FileName, Is.EqualTo("ownership_task.v0.2.json"));
            Assert.That(t.Keys.OrderBy(k => k, StringComparer.Ordinal), Is.EqualTo(new[]
                { "difference", "done", "final_choice", "final_choice_resemblance", "rating", "rating_resemblance", "viewing_intro" }));
            foreach (var k in t.Keys)
            {
                Assert.That(t[k], Is.Not.Null.And.Not.Empty, k);
                Assert.That(t.Status(k), Is.EqualTo("draft"), k + " status");
                foreach (var banned in new[] { "치료", "내담자", "진단" })
                    Assert.That(t[k].Contains(banned), Is.False, $"{k}: '{banned}' 표현 금지(AGENTS.md 8)");
            }
            Assert.That(t["rating"], Does.Contain("1(전혀 내 것 같지 않다)").And.Contain("7(완전히 내 것 같다)"));
            Assert.That(t.RatingText("resemblance"), Does.Contain("떠올린 모습과").And.Contain("닮았").And.Contain("1(").And.Contain("7("));
            Assert.That(t.RatingText("mine"), Is.EqualTo(t["rating"]));
            Assert.That(t.FinalChoiceText("resemblance", 9), Does.StartWith("9개 중").And.Contain("닮은"));
            Assert.That(t.FinalChoiceText("mine", 7), Does.StartWith("7개 중").And.Contain("'내 것'"));
            foreach (var k in new[] { "rating_resemblance", "final_choice_resemblance" })
                Assert.That(t.Source(k), Is.EqualTo("docs/rq-v2-proposal.md 3.5 (초안, IRB 검토 전)"), k + " source");
            foreach (var item in new[] { "resemblance", "mine" })
                foreach (var n in new[] { 5, 7, 9 })
                    Assert.That(t.Problems(item, n), Is.Empty, $"{item} n={n}");
            Assert.Throws<FormatException>(() => OwnershipTaskText.Parse("{\"version\":\"0.1\",\"texts\":{}}"), "빠진 문구는 오류");
            Assert.That(t.DraftKeys.Count, Is.EqualTo(7), "지금 문구 7개는 모두 draft");
            Assert.That(OwnershipRunner.DraftNotice(t, false), Does.Contain("7/7"), "실험자 화면 경고 줄");
        }

        // 0.1 문구 파일은 0.2 이전 세션 재현용으로 남는다: '내 것' 문항·조건 5개에서만 쓸 수 있다.
        [Test]
        public void Old_task_text_file_still_loads_but_only_fits_mine_with_five_conditions()
        {
            var t = OwnershipTaskText.Load(Path.Combine(Application.streamingAssetsPath, "IFS", "ownership_task.v0.json"));
            Assert.That(t.Version, Is.EqualTo("0.1"));
            Assert.That(t.Problems("mine", 5), Is.Empty);
            Assert.That(t.Problems("mine", 9).Single(), Does.Contain("{n}"), "\"다섯 개 중\" 문구로 9개를 물을 수 없다");
            Assert.That(t.Problems("resemblance", 5).Count, Is.EqualTo(2), "닮음 문구 두 개가 없다");
            Assert.That(t.FinalChoiceText("mine", 5), Is.EqualTo(t["final_choice"]));
        }

        static OwnershipTaskText TaskText(params (string key, string status)[] items)
        {
            var texts = new JObject();
            foreach (var k in OwnershipTaskText.RequiredKeys) texts[k] = new JObject { ["text"] = "합성 " + k, ["status"] = "spec", ["source"] = "합성" };
            foreach (var (key, status) in items) texts[key]["status"] = status;
            return OwnershipTaskText.Parse(new JObject { ["version"] = "9", ["texts"] = texts }.ToString(), "synthetic.json");
        }

        [Test]
        public void Draft_phrases_are_listed_warned_and_refused_only_when_required()
        {
            var mixed = TaskText(("rating", "draft"), ("done", "draft"));
            Assert.That(mixed.DraftKeys, Is.EqualTo(new[] { "done", "rating" }), "이름순");
            Assert.That(mixed.HasDraft, Is.True);
            Assert.That(OwnershipRunner.DraftNotice(mixed, false), Does.Contain("2/5").And.Contain("done, rating"));
            Assert.That(OwnershipRunner.SpecPhraseRefusal(mixed, false), Is.Null, "기본(requireSpecPhrases 꺼짐)은 경고만");
            Assert.That(OwnershipRunner.SpecPhraseRefusal(mixed, true), Does.Contain("requireSpecPhrases"), "켜면 시작 거부");

            var spec = TaskText();
            Assert.That(spec.HasDraft, Is.False);
            Assert.That(OwnershipRunner.DraftNotice(spec, true), Is.Null);
            Assert.That(OwnershipRunner.SpecPhraseRefusal(spec, true), Is.Null, "모두 spec이면 켜도 시작");
            Assert.That(new OwnershipConfig().requireSpecPhrases, Is.False, "기본 꺼짐");
        }

        [Test]
        public void Participant_text_wraps_at_spaces()
        {
            string w = ParticipantTextDisplay.Wrap("가나다 라마바 사아자 차카타", 7);
            Assert.That(w, Is.EqualTo("가나다 라마바\n사아자 차카타"));
        }

        // ── 기하 ─────────────────────────────────────────────────────────
        [Test]
        public void Gaze_angle_and_distance_follow_the_contract_definition()
        {
            // 정면(+Z)을 보는 머리, 형상이 정면 1 m → 0°, 오른쪽 1 m → 90°
            OwnershipGeometry.DistanceAngle(0, 1.6, 0, 0, 0, 0, 1, 0, 1.6, 1, out double d, out double a);
            Assert.That(d, Is.EqualTo(1).Within(1e-9));
            Assert.That(a, Is.EqualTo(0).Within(1e-6));
            OwnershipGeometry.DistanceAngle(0, 1.6, 0, 0, 0, 0, 1, 1, 1.6, 0, out _, out a);
            Assert.That(a, Is.EqualTo(90).Within(1e-6));
            // 머리를 오른쪽으로 90° 돌리면(+Y축 회전) 오른쪽 형상이 정면
            double s = Math.Sin(Math.PI / 4);
            OwnershipGeometry.DistanceAngle(0, 1.6, 0, 0, s, 0, s, 1, 1.6, 0, out _, out a);
            Assert.That(a, Is.EqualTo(0).Within(1e-6));
        }

        [Test]
        public void Arc_layout_is_centered_left_to_right_and_avoids_overlap()
        {
            var angles = OwnershipGeometry.CenteredAngles(5, 30);
            Assert.That(angles, Is.EqualTo(new[] { -60.0, -30.0, 0.0, 30.0, 60.0 }));
            Assert.That(OwnershipGeometry.CenteredAngles(2, 30), Is.EqualTo(new[] { -15.0, 15.0 }));
            OwnershipGeometry.ArcPoint(0, 0, 0, -90, 2, out double x, out double z);
            Assert.That(x, Is.EqualTo(-2).Within(1e-9), "음의 각 = 왼쪽(−X)");
            Assert.That(z, Is.EqualTo(0).Within(1e-9));
            double r = OwnershipGeometry.MinRadiusWithoutOverlap(30, 0.7, 0.1);
            double chord = 2 * r * Math.Sin(15 * Math.PI / 180);
            Assert.That(chord, Is.EqualTo(0.8).Within(1e-9), "이웃 중심 거리 = 폭 + 틈");
        }
    }
}
