// motion.type(22종) → 절차적 움직임 9묶음 표. SpecMotion(움직임)과 변형본 생성기(유무 뒤집기)가 같은 표를 쓴다.
// UnityEngine에 의존하지 않는다(dotnet 테스트 가능). 표를 바꾸면 SpecMotion의 움직임과 docs도 함께 본다.
using System.Collections.Generic;

namespace IFS.SceneSpec
{
    public enum MotionGroup { Still, Sway, Tremble, Pulse, Drift, Sink, Spin, Expand, Approach }

    public static class MotionGroups
    {
        public static readonly Dictionary<string, MotionGroup> ByType = new Dictionary<string, MotionGroup>
        {
            { "still", MotionGroup.Still },
            { "swaying", MotionGroup.Sway }, { "sloshing", MotionGroup.Sway }, { "rippling", MotionGroup.Sway },
            { "churning", MotionGroup.Sway },
            { "trembling", MotionGroup.Tremble }, { "vibrating", MotionGroup.Tremble }, { "wriggling", MotionGroup.Tremble },
            { "pounding", MotionGroup.Pulse },
            { "moving", MotionGroup.Drift }, { "drifting", MotionGroup.Drift }, { "floating", MotionGroup.Drift },
            { "rising", MotionGroup.Drift },
            { "sinking", MotionGroup.Sink }, { "settling", MotionGroup.Sink }, { "collapsing", MotionGroup.Sink },
            { "rotating", MotionGroup.Spin }, { "circling", MotionGroup.Spin },
            { "spreading", MotionGroup.Expand }, { "scattering", MotionGroup.Expand },
            { "approaching", MotionGroup.Approach }, { "pushing", MotionGroup.Approach },
        };

        public static bool TryGet(string type, out MotionGroup group) => ByType.TryGetValue(type ?? "still", out group);
    }
}
