// motion.type(22종) → 절차적 움직임 9묶음. motion.speed(0–1) → 주기 0.1–1.5 Hz.
// 부모(배치)와 자식(크기·자세)을 건드리지 않도록 가운데 'motion' 피벗만 움직인다.
// 묶음 표(MotionGroup·MotionGroups)는 UnityEngine 없이 쓰도록 SceneSpec/MotionGroups.cs에 있다(변형본 생성기와 공유).
using System.Collections.Generic;
using UnityEngine;

namespace IFS.SceneSpec
{
    [AddComponentMenu("")]
    public sealed class SpecMotion : MonoBehaviour
    {
        public static readonly Dictionary<string, MotionGroup> Groups = MotionGroups.ByType;

        [SerializeField] string motionType = "still";
        [Range(0f, 1f)] [SerializeField] float speed = 0.5f;
        [Tooltip("움직임 폭(m). 회전은 각도로 환산")] [SerializeField] float amplitude = 0.05f;

        MotionGroup _group;
        float _t;

        public MotionGroup Group => _group;

        /// <returns>모르는 motion.type이면 false(정지로 둔다).</returns>
        public bool Configure(string type, float speed01)
        {
            motionType = type;
            speed = Mathf.Clamp01(speed01);
            bool known = Groups.TryGetValue(type ?? "still", out _group);
            if (!known) _group = MotionGroup.Still;
            ResetPose();
            return known;
        }

        void ResetPose()
        {
            transform.localPosition = Vector3.zero;
            transform.localRotation = Quaternion.identity;
            transform.localScale = Vector3.one;
            _t = 0f;
        }

        void Update()
        {
            if (_group == MotionGroup.Still) return;
            _t += Time.deltaTime;
            float hz = Mathf.Lerp(0.1f, 1.5f, speed);
            float w = 2f * Mathf.PI * hz * _t;
            float ease = 0.5f - 0.5f * Mathf.Cos(w);   // 0 → 1 → 0
            switch (_group)
            {
                case MotionGroup.Sway:
                    transform.localRotation = Quaternion.Euler(0f, 0f, Mathf.Sin(w) * 12f);
                    break;
                case MotionGroup.Tremble:
                    float n = _t * 20f * hz;
                    transform.localPosition = new Vector3(Mathf.PerlinNoise(n, 0f) - 0.5f, Mathf.PerlinNoise(0f, n) - 0.5f, 0f) * amplitude * 0.4f;
                    break;
                case MotionGroup.Pulse:
                    transform.localScale = Vector3.one * (1f + 0.08f * Mathf.Sin(w));
                    break;
                case MotionGroup.Drift:
                    transform.localPosition = Vector3.up * (Mathf.Sin(w) * amplitude);
                    break;
                case MotionGroup.Sink:
                    transform.localPosition = Vector3.down * (ease * amplitude * 2f);
                    break;
                case MotionGroup.Spin:
                    transform.localRotation = Quaternion.Euler(0f, _t * 90f * hz, 0f);
                    break;
                case MotionGroup.Expand:
                    transform.localScale = Vector3.one * (1f + 0.15f * ease);
                    break;
                case MotionGroup.Approach:   // 부모가 참여자를 보고 있으므로 +z가 참여자 쪽
                    transform.localPosition = Vector3.forward * (ease * amplitude * 3f);
                    break;
            }
        }
    }
}
