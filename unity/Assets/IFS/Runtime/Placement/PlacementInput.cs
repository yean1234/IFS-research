// 참여자 입력(배치 실험). 데스크톱 모의 조작(DesktopPlacementInput)·자동 시행·XR 컨트롤러(XrPlacementInput)가 같은 모양의 한 프레임 입력을 낸다.
// 러너는 이 인터페이스만 본다. 어느 것을 쓸지는 PlacementInputSelection(설정 inputMode)이 정한다.
// 실험자 입력(평정 숫자·다음·중단)은 여기 넣지 않는다(실험자 키보드·화면이 따로 맡는다).
// UnityEngine에 의존하지 않는다.
namespace IFS.SceneSpec.Placement
{
    /// <summary>한 프레임의 참여자 입력. 좌표는 세계 좌표(미터).</summary>
    public struct PlacementInputFrame
    {
        /// <summary>광선이 있는가(데스크톱: 마우스 커서 광선, XR: 컨트롤러 광선).</summary>
        public bool HasRay;
        public PVec3 RayOrigin;
        public PVec3 RayDirection;
        /// <summary>이 프레임에 잡기 버튼을 눌렀다(눌린 순간).</summary>
        public bool GrabDown;
        /// <summary>잡기 버튼을 누르고 있다(떼면 놓는다).</summary>
        public bool GrabHeld;
        /// <summary>당기기/밀기 축(−1..1). + = 밀기(광선 원점에서 멀어짐). XR 스틱 앞뒤, 데스크톱 E/Q.</summary>
        public double PushPullAxis;
        /// <summary>이 프레임의 즉시 거리 변화(m). + = 밀기. 데스크톱 휠 한 칸 등.</summary>
        public double PushPullDeltaM;
        /// <summary>확인 버튼을 눌렀다(직접 배치: "여기에 둔다", 가리켜 지정: 가리킨 점 확정).</summary>
        public bool ConfirmDown;
        /// <summary>멈춤 거리 버튼을 눌렀다(눌린 순간).</summary>
        public bool StopDown;
        /// <summary>멈춤 거리 버튼을 누르고 있다(모르면 false). 세션은 직전 프레임에 눌려 있지 않았을 때의 StopDown만
        /// 누름으로 센다 — 시행 시작 전부터 누르고 있던 버튼이 시행을 바로 멈추지 않게(눌림 상태를 StopDown으로 주는 구현도 막는다).</summary>
        public bool StopHeld;
        /// <summary>평정 고르기(참여자 컨트롤러, 설정 participantRatesWithController): 이 프레임에 썸스틱을 왼쪽(−1)·오른쪽(+1)으로
        /// 젖힌 순간. 0 = 없음. 데스크톱·자동 시행은 쓰지 않는다.</summary>
        public int RateStep;
        /// <summary>평정 확정(참여자 컨트롤러): 이 프레임에 트리거를 누른 순간.</summary>
        public bool RateSubmitDown;
    }

    public interface IPlacementInput
    {
        /// <summary>desktop | xr (manifest의 inputSource).</summary>
        string SourceName { get; }
        /// <summary>이번 프레임 입력을 읽는다(프레임마다 한 번).</summary>
        PlacementInputFrame Read();
        /// <summary>꺼 두면 입력을 받지 않는다(실험자가 글자를 입력할 때).</summary>
        bool Enabled { get; set; }
    }
}
