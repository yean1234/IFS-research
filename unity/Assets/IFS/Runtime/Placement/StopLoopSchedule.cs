// 멈춤 거리 반복 멈춤(G60-2, stopMode loop)의 라운드 계획. 연습 라운드 뒤 본 라운드, 출발 방향은 라운드마다 번갈아 둔다
// (첫 방향 = 설정 stopFirstDirection, 기본은 참여자 번호 홀짝). 출발 거리는 [stopLoopStartMinM, stopLoopStartMaxM]에서
// 참여자 번호를 시드로 한 의사난수로 고른다(조정법에서 출발값이 닻이 되는 것을 줄이려고).
// 의사난수는 System.Random을 쓰지 않고 여기서 직접 구현한다(splitmix64로 시드를 펴고 xorshift64*로 뽑음) — 정수 연산만 써서
// Unity(Mono)와 dotnet에서 같은 수열이 나온다. 출발 거리는 1 mm 단위로 반올림해 기록과 계획이 정확히 같다.
// 2026-11-28 G83(연습 1 + 본 1): 규칙은 그대로라 연습 = 첫 방향, 본 라운드 = 그 반대 방향이다. 기본(by_participant)이면 홀수 번호는
//   연습 approach·본 recede, 짝수 번호는 연습 recede·본 approach(본 라운드 출발 방향이 참여자 사이에서 반반). 본 라운드 출발 거리는
//   수열의 두 번째 값이다(예전 4라운드 계획의 앞 두 라운드와 같은 값).
// UnityEngine에 의존하지 않는다.
using System;
using System.Collections.Generic;

namespace IFS.SceneSpec.Placement
{
    public sealed class StopRoundPlan
    {
        /// <summary>1부터, 연습 포함 전체 번호(stoprounds.csv의 round).</summary>
        public int Round;
        public bool Practice;
        /// <summary>출발 방향: approach(가까워지며 출발) | recede(멀어지며 출발).</summary>
        public string StartDirection;
        /// <summary>출발 거리(m, 1 mm 단위).</summary>
        public double StartM;
        public bool StartsApproaching => StartDirection == PlacementConfig.DirectionApproach;
    }

    /// <summary>xorshift64*(Vigna 2016). 시드는 splitmix64로 편다(0 상태를 피함). 정수 연산만 — 런타임마다 같은 수열.</summary>
    public sealed class XorShift64Star
    {
        ulong _s;

        public XorShift64Star(ulong seed)
        {
            ulong z = seed + 0x9E3779B97F4A7C15UL;   // splitmix64 한 번
            z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9UL;
            z = (z ^ (z >> 27)) * 0x94D049BB133111EBUL;
            z ^= z >> 31;
            _s = z == 0 ? 0x9E3779B97F4A7C15UL : z;
        }

        public ulong NextULong()
        {
            ulong x = _s;
            x ^= x >> 12;
            x ^= x << 25;
            x ^= x >> 27;
            _s = x;
            return x * 0x2545F4914F6CDD1DUL;
        }

        /// <summary>[0, 1) 균등. 위 53비트만 쓴다(정확히 표현되는 값만 나옴).</summary>
        public double NextDouble() => (NextULong() >> 11) * (1.0 / 9007199254740992.0);
    }

    public static class StopLoopSchedule
    {
        /// <summary>manifest stopDistance.loop.startRule에 남길 규칙 이름.</summary>
        public const string StartRule = "xorshift64star(splitmix64(participantNumber)), uniform [startMinM, startMaxM], round 0.001 m";

        public static List<StopRoundPlan> Build(PlacementConfig cfg, int participantNumber)
        {
            if (cfg == null) throw new ArgumentNullException(nameof(cfg));
            string first = cfg.FirstDirectionFor(participantNumber);
            string second = first == PlacementConfig.DirectionApproach ? PlacementConfig.DirectionRecede : PlacementConfig.DirectionApproach;
            var rng = new XorShift64Star(unchecked((ulong)participantNumber));
            var list = new List<StopRoundPlan>();
            int total = Math.Max(0, cfg.stopLoopPracticeRounds) + Math.Max(0, cfg.stopLoopRounds);
            for (int i = 0; i < total; i++)
            {
                double u = rng.NextDouble();
                double start = Math.Round(cfg.stopLoopStartMinM + (cfg.stopLoopStartMaxM - cfg.stopLoopStartMinM) * u, 3, MidpointRounding.AwayFromZero);
                list.Add(new StopRoundPlan
                {
                    Round = i + 1,
                    Practice = i < cfg.stopLoopPracticeRounds,
                    StartDirection = i % 2 == 0 ? first : second,
                    StartM = start,
                });
            }
            return list;
        }
    }
}
