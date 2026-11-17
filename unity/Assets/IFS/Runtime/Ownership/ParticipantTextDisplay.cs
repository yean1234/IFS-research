// 참여자에게 보이는 글(설계 2.1): 월드 공간 TextMesh + OS 동적 폰트(맑은 고딕 등).
// uGUI·TextMeshPro·폰트 에셋 없이 쓴다. 한글 폰트를 OS에서 찾지 못하면 내장 폰트로 대신하고 경고를 남긴다
// (그때 한글이 보이지 않을 수 있다 — 실험자 화면·events.csv에 경고).
// 글은 머리를 따라다니지 않고 정해진 자리에 선다(VR에서 머리 고정 글은 불편하다).
using System.Collections.Generic;
using System.Text;
using UnityEngine;

namespace IFS.SceneSpec.Ownership
{
    [DisallowMultipleComponent]
    [AddComponentMenu("IFS/Ownership/Participant Text Display")]
    public sealed class ParticipantTextDisplay : MonoBehaviour
    {
        [Tooltip("앞에서부터 OS에 있는 첫 폰트를 쓴다")]
        [SerializeField] string[] osFontNames = { "Malgun Gothic", "맑은 고딕", "Apple SD Gothic Neo", "Noto Sans CJK KR", "Noto Sans KR", "NanumGothic" };
        [SerializeField] int fontSize = 64;
        [Tooltip("글자 크기(m 단위 배율). 0.01 × fontSize 64 ≈ 글자 높이 6 cm")]
        [SerializeField] float characterSize = 0.01f;
        [Tooltip("한 줄 최대 글자 수(띄어쓰기에서 줄을 바꾼다)")]
        [SerializeField] int wrapChars = 22;
        [SerializeField] Color textColor = new Color(0.08f, 0.08f, 0.1f, 1f);
        [SerializeField] float labelCharacterSize = 0.014f;

        Font _font;
        TextMesh _main;
        readonly List<TextMesh> _labels = new List<TextMesh>();

        /// <summary>폰트를 OS에서 찾지 못했을 때의 경고(없으면 null).</summary>
        public string FontWarning { get; private set; }
        public string FontName { get; private set; }
        public string CurrentText => _main != null && _main.gameObject.activeSelf ? _main.text : null;

        public Font EnsureFont()
        {
            if (_font != null) return _font;
            var installed = new HashSet<string>(Font.GetOSInstalledFontNames() ?? new string[0]);
            string found = null;
            foreach (var n in osFontNames)
                if (installed.Contains(n)) { found = n; break; }
            if (found != null)
            {
                _font = Font.CreateDynamicFontFromOSFont(found, fontSize);
                FontName = found;
            }
            if (_font == null)
            {
                _font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
                FontName = "LegacyRuntime.ttf";
                FontWarning = "한글 OS 폰트(" + string.Join(", ", osFontNames) + ")를 찾지 못해 내장 폰트로 대신함 — 한글이 보이지 않을 수 있음";
                Debug.LogWarning("[Ownership] " + FontWarning, this);
            }
            return _font;
        }

        TextMesh Make(string name, float charSize)
        {
            var go = new GameObject(name);
            go.transform.SetParent(transform, false);
            var tm = go.AddComponent<TextMesh>();
            var font = EnsureFont();
            tm.font = font;
            tm.fontSize = fontSize;
            tm.characterSize = charSize;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.alignment = TextAlignment.Center;
            tm.color = textColor;
            var r = go.GetComponent<MeshRenderer>();
            if (r != null && font != null) r.sharedMaterial = font.material;
            go.SetActive(false);
            return tm;
        }

        /// <summary>글을 pos에 세운다. 글의 앞면이 viewer 쪽을 보게 돌린다.</summary>
        public void Show(string text, Vector3 pos, Vector3 viewer)
        {
            if (_main == null) _main = Make("participant text", characterSize);
            _main.text = Wrap(text, wrapChars);
            Place(_main.transform, pos, viewer);
            _main.gameObject.SetActive(true);
        }

        public void Hide()
        {
            if (_main != null) _main.gameObject.SetActive(false);
        }

        public void ShowLabel(int index, string text, Vector3 pos, Vector3 viewer)
        {
            while (_labels.Count <= index) _labels.Add(Make("label " + _labels.Count, labelCharacterSize));
            var tm = _labels[index];
            tm.text = text;
            Place(tm.transform, pos, viewer);
            tm.gameObject.SetActive(true);
        }

        public void HideLabels()
        {
            foreach (var l in _labels) if (l != null) l.gameObject.SetActive(false);
        }

        public void HideAll()
        {
            Hide();
            HideLabels();
        }

        static void Place(Transform t, Vector3 pos, Vector3 viewer)
        {
            t.position = pos;
            var away = pos - viewer;   // TextMesh는 +Z 쪽에서 볼 때 바로 읽힌다 → 앞(+Z)이 보는 사람 반대쪽
            away.y = 0f;
            t.rotation = away.sqrMagnitude > 1e-6f ? Quaternion.LookRotation(away.normalized, Vector3.up) : Quaternion.identity;
        }

        /// <summary>띄어쓰기에서 줄을 바꾼다(TextMesh는 자동 줄바꿈이 없다). 이미 있는 줄바꿈은 지킨다.</summary>
        public static string Wrap(string text, int maxChars)
        {
            if (string.IsNullOrEmpty(text) || maxChars <= 0) return text ?? "";
            var sb = new StringBuilder();
            foreach (var para in text.Replace("\r\n", "\n").Split('\n'))
            {
                if (sb.Length > 0) sb.Append('\n');
                int line = 0;
                foreach (var word in para.Split(' '))
                {
                    if (word.Length == 0) continue;
                    if (line > 0 && line + 1 + word.Length > maxChars) { sb.Append('\n'); line = 0; }
                    else if (line > 0) { sb.Append(' '); line++; }
                    sb.Append(word);
                    line += word.Length;
                }
            }
            return sb.ToString();
        }
    }
}
