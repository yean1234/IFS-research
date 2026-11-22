// 멈춤 거리 시행 순서(X49). 연습 시행 뒤 본시행, 둘 다 방향을 번갈아 둔다. 첫 방향은 설정(stopFirstDirection).
// UnityEngine에 의존하지 않는다.
using System.Collections.Generic;

namespace IFS.SceneSpec.Placement
{
    public sealed class StopTrialPlan
    {
        /// <summary>1부터, 연습 포함 전체 번호(stopdistance.csv의 trial).</summary>
        public int Trial;
        public bool Practice;
        /// <summary>approach | recede</summary>
        public string Direction;
        /// <summary>같은 방향 시행 가운데 몇 번째인지(0부터, 연습 포함). 자동 시행 스크립트가 쓴다.</summary>
        public int DirectionIndex;
        public double StartM;
        public bool IsApproach => Direction == PlacementConfig.DirectionApproach;
    }

    public static class StopDistanceSchedule
    {
        public static List<StopTrialPlan> Build(PlacementConfig cfg, int participantNumber)
        {
            string first = cfg.FirstDirectionFor(participantNumber);
            string second = first == PlacementConfig.DirectionApproach ? PlacementConfig.DirectionRecede : PlacementConfig.DirectionApproach;
            var list = new List<StopTrialPlan>();
            int approachN = 0, recedeN = 0;
            void Add(string dir, bool practice)
            {
                bool app = dir == PlacementConfig.DirectionApproach;
                list.Add(new StopTrialPlan
                {
                    Trial = list.Count + 1, Practice = practice, Direction = dir,
                    DirectionIndex = app ? approachN++ : recedeN++,
                    StartM = app ? cfg.stopApproachStartM : cfg.stopRecedeStartM,
                });
            }
            for (int i = 0; i < cfg.stopPracticeTrials; i++) Add(i % 2 == 0 ? first : second, true);
            for (int i = 0; i < 2 * cfg.stopTrialsPerDirection; i++) Add(i % 2 == 0 ? first : second, false);
            return list;
        }
    }
}
