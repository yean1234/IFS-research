// 데스크톱 모의 조작(헤드셋 없이 개발·시연용). 기존 Input Manager만 쓴다(패키지 추가 없음).
//   광선     : 카메라에서 마우스 커서 쪽으로
//   잡기     : 마우스 왼쪽 단추를 누르고 있는 동안(떼면 놓는다)
//   당기기/밀기: 휠(한 칸 = wheelStepM) 또는 E(밀기)·Q(당기기)를 누르고 있기
//   확인     : F ("여기에 둔다" / 가리킨 점 확정)
//   멈춤 거리 버튼: Space
// HeadPoseProvider의 모의 조작(마우스 오른쪽 드래그 = 둘러보기, WASD = 이동)과 겹치지 않는다.
// XR 컨트롤러로 바꿀 때는 IPlacementInput을 구현한 컴포넌트를 하나 더 만들어 러너에 연결한다(unity/README.md).
using UnityEngine;

namespace IFS.SceneSpec.Placement
{
    [DisallowMultipleComponent]
    [AddComponentMenu("IFS/Placement/Desktop Placement Input")]
    public sealed class DesktopPlacementInput : MonoBehaviour, IPlacementInput
    {
        public const string Source = "desktop";

        [Tooltip("광선을 쏠 카메라. 비우면 Camera.main")]
        [SerializeField] Camera rayCamera = null;
        [Tooltip("휠 한 칸(Mouse ScrollWheel 축 0.1)당 거리 변화(m)")]
        [SerializeField] float wheelStepM = 0.15f;

        public string SourceName => Source;
        public bool Enabled { get; set; } = true;

        public void Configure(Camera cam) => rayCamera = cam;

        public PlacementInputFrame Read()
        {
            var f = new PlacementInputFrame();
            if (!Enabled) return f;
            var cam = rayCamera != null ? rayCamera : Camera.main;
            if (cam != null)
            {
                var ray = cam.ScreenPointToRay(Input.mousePosition);
                f.HasRay = true;
                f.RayOrigin = PlacementSpace.FromUnity(ray.origin);
                f.RayDirection = PlacementSpace.FromUnity(ray.direction);
            }
            f.GrabDown = Input.GetMouseButtonDown(0);
            f.GrabHeld = Input.GetMouseButton(0);
            f.PushPullDeltaM = Input.GetAxis("Mouse ScrollWheel") * 10f * wheelStepM;
            f.PushPullAxis = (Input.GetKey(KeyCode.E) ? 1.0 : 0.0) - (Input.GetKey(KeyCode.Q) ? 1.0 : 0.0);
            f.ConfirmDown = Input.GetKeyDown(KeyCode.F);
            f.StopDown = Input.GetKeyDown(KeyCode.Space);
            return f;
        }
    }
}
