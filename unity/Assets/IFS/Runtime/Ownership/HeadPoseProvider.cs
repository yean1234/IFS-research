// 머리 자세 공급(설계 2.1). 카메라(머리) 변환을 움직이고, 지금 자세와 공급원(xr | desktop)을 알려 준다.
//   xr      : UnityEngine.XR.InputDevices의 Head 노드가 유효하면 그 위치·회전을 카메라 로컬 자세로 넣는다.
//             (XR 플러그인 설치·헤드셋 연결은 사람이 따로 하는 단계 — unity/README.md 「소유감 실험」. 실기 미검증)
//   desktop : 헤드셋이 없으면 데스크톱 모의 조작. 마우스 오른쪽 드래그 = 둘러보기, WASD = 수평 이동(눈높이 유지).
//   scripted: 자동 시행(검증용). 키·마우스 없이 정해진 경로로 천천히 둘러본다(기록 공급원은 desktop).
// 기존 Input Manager(activeInputHandler 0)를 쓴다. 패키지를 더하지 않는다.
using UnityEngine;
using UnityEngine.XR;

namespace IFS.SceneSpec.Ownership
{
    [DisallowMultipleComponent]
    [DefaultExecutionOrder(-50)]
    [AddComponentMenu("IFS/Ownership/Head Pose Provider")]
    public sealed class HeadPoseProvider : MonoBehaviour
    {
        public const string SourceXr = "xr";
        public const string SourceDesktop = "desktop";

        [Tooltip("움직일 머리(카메라) 변환. 비우면 이 GameObject")]
        [SerializeField] Transform target = null;
        [Tooltip("XR Head 노드를 찾으면 그것을 쓴다")]
        [SerializeField] bool useXrWhenAvailable = true;
        [Header("데스크톱 모의 조작")]
        [Tooltip("마우스 이동 1단위당 회전(도)")] [SerializeField] float lookDegreesPerUnit = 2f;
        [Tooltip("WASD 이동 속도(m/s)")] [SerializeField] float moveSpeed = 1.0f;
        [Tooltip("내려다보기·올려다보기 한계(도)")] [SerializeField] float pitchLimit = 80f;

        float _yaw, _pitch;
        bool _desktopInit;
        bool _scripted;
        Vector3 _scriptBase;
        float _scriptYawBase;

        /// <summary>xr | desktop</summary>
        public string Source { get; private set; } = SourceDesktop;
        /// <summary>꺼 두면 데스크톱 조작을 받지 않는다(실험자가 글자를 입력할 때).</summary>
        public bool DesktopInputEnabled { get; set; } = true;
        public bool Scripted => _scripted;

        public Transform Target => target != null ? target : transform;
        public Vector3 Position => Target.position;
        public Quaternion Rotation => Target.rotation;

        void Update()
        {
            if (_scripted) return;
            Step(Time.deltaTime);
        }

        /// <summary>한 프레임: XR이 있으면 XR, 없으면 데스크톱 조작.</summary>
        public void Step(float dt)
        {
            if (useXrWhenAvailable && TryReadXrHead(out var p, out var r))
            {
                Target.localPosition = p;
                Target.localRotation = r;
                Source = SourceXr;
                return;
            }
            Source = SourceDesktop;
            if (!_desktopInit)
            {
                var e = Target.rotation.eulerAngles;
                _yaw = e.y;
                _pitch = e.x > 180f ? e.x - 360f : e.x;
                _desktopInit = true;
            }
            if (!DesktopInputEnabled) return;
            if (Input.GetMouseButton(1))
            {
                _yaw += Input.GetAxis("Mouse X") * lookDegreesPerUnit;
                _pitch = Mathf.Clamp(_pitch - Input.GetAxis("Mouse Y") * lookDegreesPerUnit, -pitchLimit, pitchLimit);
            }
            float f = (Input.GetKey(KeyCode.W) ? 1f : 0f) - (Input.GetKey(KeyCode.S) ? 1f : 0f);
            float s = (Input.GetKey(KeyCode.D) ? 1f : 0f) - (Input.GetKey(KeyCode.A) ? 1f : 0f);
            var yawRot = Quaternion.Euler(0f, _yaw, 0f);
            Target.position = Target.position + yawRot * new Vector3(s, 0f, f) * (moveSpeed * dt);
            Target.rotation = Quaternion.Euler(_pitch, _yaw, 0f);
        }

        /// <summary>자동 시행: 지금 자세를 기준으로 정해진 경로를 따른다(키 입력 없음).</summary>
        public void BeginScripted()
        {
            _scripted = true;
            _scriptBase = Target.position;
            _scriptYawBase = Target.rotation.eulerAngles.y;
            Source = SourceDesktop;
        }

        /// <summary>자동 시행 경로: 좌우 ±25° 둘러보기, 옆 ±0.15 m, 앞뒤 ±0.10 m(주기가 서로 달라 겹치지 않음).</summary>
        public void ScriptedPose(double t)
        {
            float tf = (float)t;
            float yaw = _scriptYawBase + 25f * Mathf.Sin(2f * Mathf.PI * tf / 6f);
            float pitch = 8f * Mathf.Sin(2f * Mathf.PI * tf / 11f);
            var yawRot = Quaternion.Euler(0f, _scriptYawBase, 0f);
            var offset = new Vector3(0.15f * Mathf.Sin(2f * Mathf.PI * tf / 9f), 0f, 0.10f * Mathf.Sin(2f * Mathf.PI * tf / 7f));
            Target.position = _scriptBase + yawRot * offset;
            Target.rotation = Quaternion.Euler(pitch, yaw, 0f);
        }

        public static bool TryReadXrHead(out Vector3 position, out Quaternion rotation)
        {
            position = Vector3.zero;
            rotation = Quaternion.identity;
            var device = InputDevices.GetDeviceAtXRNode(XRNode.Head);
            if (!device.isValid) return false;
            return device.TryGetFeatureValue(CommonUsages.devicePosition, out position)
                   && device.TryGetFeatureValue(CommonUsages.deviceRotation, out rotation);
        }
    }
}
