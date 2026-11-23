// 실험자 화면의 위험한 동작(세션 중단)을 두 번에 나눠 누르게 하는 표현 계층 상태(2026-11-23 G44 화면 개선,
// ui-ux-pro-max §8 confirmation-dialogs·destructive-emphasis). UnityEngine에 의존하지 않는다.
//   · 첫 누름(Arm): 확인 상자를 연다. 그때의 맥락(러너 단계 + 세션 단계)을 기억한다.
//   · 둘째 누름(Confirm): 같은 맥락이면 true(호출자가 기존 runner.PressAbort()를 부른다), 맥락이 바뀌었으면 false.
//     단계가 넘어가 버린 뒤에 열린 확인 상자로 다른 단계를 중단하지 않게 — 맥락이 바뀌면 상자는 저절로 닫힌다.
//   · 취소(Cancel): 닫는다.
// 버튼이 부르는 러너 함수(PressAbort)와 Esc 키(러너가 직접 읽음)는 바꾸지 않는다.
namespace IFS.SceneSpec.Placement
{
    public sealed class PlacementConfirmStep
    {
        /// <summary>확인 상자를 연 맥락. 닫혀 있으면 null.</summary>
        public string ArmedFor { get; private set; }

        /// <summary>지금 맥락에서 확인 상자가 열려 있나.</summary>
        public bool IsArmed(string context) => ArmedFor != null && ArmedFor == (context ?? "");

        public void Arm(string context) => ArmedFor = context ?? "";

        public void Cancel() => ArmedFor = null;

        /// <summary>확정: 같은 맥락에서 열려 있었으면 true. 어느 경우든 상자는 닫힌다.</summary>
        public bool Confirm(string context)
        {
            bool ok = IsArmed(context);
            ArmedFor = null;
            return ok;
        }
    }
}
