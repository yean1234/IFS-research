// 참여자가 공간을 고르기(설정 environmentChoice participant)와 헤드셋/모니터 화면 나누기 규칙.
//   2026-11-28 연구 책임자 결정(뒤의 결정): 실험에서는 공간을 실험자가 설정 화면 단추로 고른다. 참여자 고르기 단계는 지우지 않고 남긴 꺼 둔 기능이다
//   (잠금 PlacementExperimentLock이 experimenter로 되돌린다 — 잠금을 끄고 인스펙터·명령줄 -environmentChoice participant로만 켠다).
//   공간 고르기: 세션 첫 단계 space_choice(PlacementSession). 세 공간(기본 neutral · 자연 nature · 우주 space)을 방아쇠로 차례로 보고,
//   세 공간을 모두 본 뒤 확인 버튼으로 정한다. 보여 주는 순서는 참여자 번호로 돌린다(Order — 첫 공간이 늘 같으면 처음 본 것이 고르기에 섞이므로).
//   실험자 Enter = 지금 보이는 공간으로 정함(참여자가 말로 고른 때, chosenBy experimenter).
//   화면 나누기: 실험자 화면(IMGUI)은 XR 눈 영상에 들어가지 않는다. 헤드셋에 실험자 화면이 보이는 것은 XR이 켜지지 않아 데스크톱으로 돌 때
//   참여자가 Link의 데스크톱 보기로 PC 화면을 보는 경우다(2026-11-28 Editor.log: XR_ERROR_FORM_FACTOR_UNAVAILABLE). 그래서
//   잠금(실험 씬)에서는 XR 없이 auto/xr 입력으로 시작하지 않고(HeadsetMissingRefusal), XR이 켜진 동안 세션 전에는 헤드셋 판에 대기 문구만 보인다.
// UnityEngine에 의존하지 않는다.
using System;
using System.Linq;

namespace IFS.SceneSpec.Placement
{
    public static class PlacementSpaceChoice
    {
        /// <summary>보여 주는 순서의 바탕(연구 책임자가 적은 순서: 기본·자연·우주).</summary>
        public static readonly string[] BaseOrder = { PlacementConfig.EnvironmentNeutral, PlacementConfig.EnvironmentNature, PlacementConfig.EnvironmentSpace };
        /// <summary>manifest environmentChoice.orderRule.</summary>
        public const string OrderRule = "rotate_by_participant/1";
        public const string ByParticipant = "participant_confirm";
        public const string ByExperimenter = "experimenter";
        public const string ByAbort = "abort";

        /// <summary>참여자 번호 n의 순서: BaseOrder를 (n − 1) mod 3만큼 돌린다(1 → 기본·자연·우주, 2 → 자연·우주·기본, 3 → 우주·기본·자연).</summary>
        public static string[] Order(int participantNumber)
        {
            int n = BaseOrder.Length;
            int k = ((participantNumber - 1) % n + n) % n;
            return Enumerable.Range(0, n).Select(i => BaseOrder[(i + k) % n]).ToArray();
        }

        // ── 헤드셋/모니터 화면 나누기 ──────────────────────────────────────
        /// <summary>세션 전(Setup·Checked)에 헤드셋 판에 보일 문구 키: XR 헤드셋이 켜져 있고 자동 시행이 아니면 대기 문구(wait), 아니면 null(판 숨김 —
        /// 데스크톱 전용 실행은 예전 그대로).</summary>
        public static string IdlePanelKey(bool sessionRunning, bool xrHeadActive, bool auto) =>
            !sessionRunning && xrHeadActive && !auto ? "wait" : null;

        /// <summary>잠금(실험 씬)인데 XR 헤드셋이 켜지지 않았고 참여자 입력이 desktop이 아니면 시작 거부 이유. 아니면 null.
        /// 헤드셋 없이 시험할 때는 참여자 입력을 desktop으로 고르면 된다(그때는 한 화면에 모두 보이는 예전 데스크톱 실행).</summary>
        public static string HeadsetMissingRefusal(bool locked, bool xrHeadActive, string inputMode, bool auto)
        {
            if (!locked || xrHeadActive || auto || inputMode == PlacementConfig.InputModeDesktop) return null;
            return "헤드셋 XR이 켜지지 않아 데스크톱으로 돌고 있습니다(Link가 꺼져 있었거나 헤드셋이 잠들어 있었음 — 콘솔의 OpenXR 오류). " +
                   "이대로면 참여자가 Link 데스크톱 보기로 이 실험자 화면(세션·참여자 번호·조건)을 볼 수 있어 시작하지 않습니다 — " +
                   "헤드셋 안에서 Link를 켠 뒤 Play를 다시 누르세요(XR이 뒤늦게 켜지면 이 오류는 저절로 사라집니다). 헤드셋 없이 시험하려면 참여자 입력을 desktop으로 고르세요";
        }

        /// <summary>CP17-4: 확인 뒤 XR 상태가 바뀌었을 때 시작 거부 줄을 고친다. previous = 지금 errors에 있는 거부(없으면 null), current = 지금 상태의 거부.
        /// 바뀌었으면 previous를 빼고 current를 더한다. 거부가 풀렸으면(previous 있음 → current 없음) cleared true(부른 쪽이 참여자 입력을 다시 고른다).
        /// 돌려주는 값 = 이제 errors에 있는 거부.</summary>
        public static string UpdateHeadsetRefusal(System.Collections.Generic.List<string> errors, string previous, string current, out bool cleared)
        {
            cleared = false;
            if (previous == current) return current;
            if (previous != null) errors.Remove(previous);
            if (current != null && !errors.Contains(current)) errors.Add(current);
            cleared = previous != null && current == null;
            return current;
        }

        /// <summary>CP17-1: 세션 중 XR이 끊겼을 때 실험자 화면 경고(빨간 글, 실험자 화면에만). 타이머·단계는 멈추지 않는다.</summary>
        public static string XrLostAlert(int lostCount) =>
            $"헤드셋 연결이 끊겼습니다(이번 세션 {lostCount}번째). 참여자가 헤드셋의 Link 데스크톱 보기로 이 PC 화면을 볼 수 있습니다. " +
            "세션 시간은 멈추지 않고 계속 갑니다 — 이 화면을 숨기려면 F1, 세션을 멈추려면 오른쪽 아래 [중단…] 또는 Esc(확인 없이 바로 중단). 다시 잡히면 이 경고는 사라지고 기록에 남습니다";
    }
}
