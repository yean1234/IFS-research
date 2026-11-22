// 참여자 안내 패널(배치 실험, 헤드셋 안에서 읽히게): 세계 공간에 고정된 판(머리를 따라다니지 않는다).
//   · 글: TextMesh + OS 동적 폰트(맑은 고딕 등 — ParticipantTextDisplay.EnsureFont와 같은 방식, uGUI·TextMeshPro 없음).
//   · 판: 옅은 회색 사각형(글 뒤 1 cm). 판 전체를 눈 쪽으로 기울여(피치 포함) 글이 눈을 똑바로 보게 한다.
//   · 평정 문항: 문항 글 + 아래에 기준점 줄(문항 범위 min–max, 기본 1–7 — 숫자와 그 아래 기준점 뜻). 참여자 컨트롤러로 고르는 중이면 그 숫자를 강조한다.
//     칸이 7개보다 많으면(예: 0–10의 11칸) 줄 전체 너비가 7칸 너비를 넘지 않게 칸을 좁힌다.
//   · 깊이: 기본 TextMesh 재질(GUI/Text Shader)은 깊이 검사 없이 모든 것 위에 그려져, 판이 물체 뒤에 있어도 글이 물체를 덮는다.
//     그래서 글 재질을 복제해 unity_GUIZTestMode = LessEqual(4)로 둔다(물체가 앞에 있으면 물체가 글을 가린다 — 글이 물체를 가리지 않게).
// 자리·크기는 러너 설정값(PlacementRunner textForwardM·textHeightM, 이 컴포넌트의 글자 크기). 실기 미검증(docs/headset-checklist.md).
using System.Collections.Generic;
using IFS.SceneSpec.Ownership;
using UnityEngine;

namespace IFS.SceneSpec.Placement
{
    [DisallowMultipleComponent]
    [AddComponentMenu("IFS/Placement/Participant Text Panel")]
    public sealed class PlacementTextPanel : MonoBehaviour
    {
        [Header("글")]
        [SerializeField] int fontSize = 64;
        [Tooltip("본문 글자 크기 배율. 0.0085 × fontSize 64 ≈ 글자 높이 5 cm(2 m에서 약 1.4°)")]
        [SerializeField] float characterSize = 0.0085f;
        [Tooltip("본문 한 줄 최대 글자 수(띄어쓰기에서 줄을 바꾼다)")]
        [SerializeField] int wrapChars = 20;
        [Tooltip("기준점 뜻 글자 크기 배율")]
        [SerializeField] float labelCharacterSize = 0.0055f;
        [Tooltip("기준점 뜻 한 줄 최대 글자 수")]
        [SerializeField] int labelWrapChars = 6;
        [Tooltip("기준점 한 칸 너비(m)")]
        [SerializeField] float columnWidthM = 0.2f;
        [Tooltip("판 가장자리 여백(m)")]
        [SerializeField] float marginM = 0.06f;
        [SerializeField] Color textColor = new Color(0.08f, 0.08f, 0.1f, 1f);
        [SerializeField] Color highlightColor = new Color(0.10f, 0.35f, 0.85f, 1f);
        [SerializeField] Color backgroundColor = new Color(0.90f, 0.90f, 0.91f, 1f);
        [Tooltip("판(배경) 보이기")]
        [SerializeField] bool showBackground = true;
        [Tooltip("글을 깊이 검사해 물체 뒤에서는 가려지게(끄면 TextMesh 기본: 모든 것 위에 그림)")]
        [SerializeField] bool depthTestText = true;

        // 글꼴 단위 → 미터(TextMesh: characterSize × fontSize × 0.1이 대략 한 글자 높이)
        const float UnitPerPx = 0.1f;
        const float LineSpacing = 1.3f;
        const float HangulAdvance = 1.0f, OtherAdvance = 0.55f;

        Font _font;
        Material _textMat, _bgMat;
        Transform _root;
        TextMesh _body;
        readonly List<TextMesh> _numbers = new List<TextMesh>();
        readonly List<TextMesh> _labels = new List<TextMesh>();
        GameObject _bg;
        string _shownKey;

        public string CurrentText { get; private set; }
        public bool Visible => _root != null && _root.gameObject.activeSelf;
        /// <summary>마지막으로 그린 판의 크기(m, 너비·높이). 테스트·점검용.</summary>
        public Vector2 PanelSizeM { get; private set; }
        /// <summary>판 중심(세계 좌표).</summary>
        public Vector3 PanelCenter => _root != null ? _root.position : Vector3.zero;

        /// <summary>쓸 글꼴(ParticipantTextDisplay.EnsureFont가 OS에서 찾은 것). null이면 내장 폰트.</summary>
        public void SetFont(Font font)
        {
            if (font == _font && font != null) return;
            _font = font;
            if (_textMat != null) { DestroySafe(_textMat); _textMat = null; }
            Rebuild();
        }

        void OnEnable() => Font.textureRebuilt += OnFontTextureRebuilt;
        void OnDisable() => Font.textureRebuilt -= OnFontTextureRebuilt;

        void OnFontTextureRebuilt(Font f)
        {
            if (f != null && f == _font && _textMat != null) _textMat.mainTexture = f.material.mainTexture;
        }

        void OnDestroy()
        {
            DestroySafe(_textMat);
            DestroySafe(_bgMat);
            if (_root != null) DestroySafe(_root.gameObject);
        }

        // ── 보이기 ───────────────────────────────────────────────────────
        /// <summary>글 한 덩어리를 center에 세운다(판이 eye를 본다).</summary>
        public void ShowText(string text, Vector3 center, Vector3 eye)
        {
            string key = "T|" + text;
            if (_shownKey == key && Visible) { Place(center, eye); return; }
            Ensure();
            _body.text = ParticipantTextDisplay.Wrap(text ?? "", wrapChars);
            CurrentText = text;
            SetScale(0, null, null);
            Layout(_body.text, 0, 0);
            Place(center, eye);
            _root.gameObject.SetActive(true);
            _shownKey = key;
        }

        /// <summary>평정 문항: 문항 글 + 기준점 줄(cursor = 참여자가 고르는 중인 값, 없으면 null).</summary>
        public void ShowItem(PlacementItem item, int? cursor, Vector3 center, Vector3 eye)
        {
            if (item == null) { Hide(); return; }
            string key = "I|" + item.Key + "|" + (cursor?.ToString() ?? "-");
            if (_shownKey == key && Visible) { Place(center, eye); return; }
            Ensure();
            _body.text = ParticipantTextDisplay.Wrap(item.Text ?? "", wrapChars);
            CurrentText = item.Text;
            int n = item.Max - item.Min + 1;
            int labelLines = SetScale(n, item, cursor);
            Layout(_body.text, n, labelLines);
            Place(center, eye);
            _root.gameObject.SetActive(true);
            _shownKey = key;
        }

        public void Hide()
        {
            if (_root != null) _root.gameObject.SetActive(false);
            CurrentText = null;
            _shownKey = null;
        }

        // ── 만들기·배치 ──────────────────────────────────────────────────
        void Ensure()
        {
            if (_root != null) return;
            var go = new GameObject("participant panel");
            go.transform.SetParent(transform, false);
            _root = go.transform;
            if (showBackground)
            {
                _bg = GameObject.CreatePrimitive(PrimitiveType.Quad);
                _bg.name = "panel background";
                _bg.transform.SetParent(_root, false);
                var col = _bg.GetComponent<Collider>();
                if (col != null) DestroySafe(col);
                var r = _bg.GetComponent<MeshRenderer>();
                if (r != null)
                {
                    _bgMat = new Material(r.sharedMaterial) { name = "IFS placement panel background" };
                    _bgMat.color = backgroundColor;
                    // 조명 방향과 상관없이 밝게(빌드에서 _EMISSION 변형이 빠지면 조명만 받는 회색 판이 된다)
                    _bgMat.EnableKeyword("_EMISSION");
                    _bgMat.SetColor("_EmissionColor", backgroundColor * 0.6f);
                    r.sharedMaterial = _bgMat;
                    r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                    r.receiveShadows = false;
                }
            }
            _body = MakeText("panel body", characterSize, TextAnchor.UpperCenter);
            go.SetActive(false);
        }

        void Rebuild()
        {
            if (_root == null) return;
            bool was = _root.gameObject.activeSelf;
            DestroySafe(_root.gameObject);
            _root = null;
            _body = null;
            _numbers.Clear();
            _labels.Clear();
            _bg = null;
            _shownKey = null;
            if (was) Ensure();
        }

        Material TextMaterial()
        {
            if (_font == null) _font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            if (_font == null) return null;
            if (!depthTestText) return _font.material;
            if (_textMat == null)
            {
                _textMat = new Material(_font.material) { name = "IFS placement panel text (depth tested)" };
                _textMat.SetFloat("unity_GUIZTestMode", 4f);   // CompareFunction.LessEqual
            }
            _textMat.mainTexture = _font.material.mainTexture;
            return _textMat;
        }

        TextMesh MakeText(string name, float charSize, TextAnchor anchor)
        {
            var go = new GameObject(name);
            go.transform.SetParent(_root, false);
            var tm = go.AddComponent<TextMesh>();
            var mat = TextMaterial();
            tm.font = _font;
            tm.fontSize = fontSize;
            tm.characterSize = charSize;
            tm.anchor = anchor;
            tm.alignment = TextAlignment.Center;
            tm.color = textColor;
            tm.richText = true;
            var r = go.GetComponent<MeshRenderer>();
            if (r != null && mat != null) r.sharedMaterial = mat;
            return tm;
        }

        /// <summary>기준점 줄을 채운다(n = 0이면 숨김). 기준점 뜻의 최대 줄 수를 돌려준다.</summary>
        int SetScale(int n, PlacementItem item, int? cursor)
        {
            while (_numbers.Count < n) _numbers.Add(MakeText("scale number " + _numbers.Count, characterSize, TextAnchor.UpperCenter));
            while (_labels.Count < n) _labels.Add(MakeText("scale label " + _labels.Count, labelCharacterSize, TextAnchor.UpperCenter));
            int maxLines = 0;
            for (int i = 0; i < _numbers.Count; i++)
            {
                bool on = i < n;
                _numbers[i].gameObject.SetActive(on);
                _labels[i].gameObject.SetActive(on);
                if (!on) continue;
                int v = item.Min + i;
                bool sel = cursor.HasValue && cursor.Value == v;
                _numbers[i].text = sel ? "<b>" + v + "</b>" : v.ToString();
                _numbers[i].color = sel ? highlightColor : textColor;
                string label = ParticipantTextDisplay.Wrap(item.AnchorAt(v) ?? "", labelWrapChars);
                _labels[i].text = label;
                _labels[i].color = sel ? highlightColor : textColor;
                maxLines = Mathf.Max(maxLines, label.Length == 0 ? 0 : label.Split('\n').Length);
            }
            return maxLines;
        }

        /// <summary>기준점 한 칸 너비(m): 7칸까지는 columnWidthM, 그보다 많으면 줄 전체가 7칸 너비가 되게 좁힌다.</summary>
        float ColumnWidth(int n) => n > 7 ? columnWidthM * 7f / n : columnWidthM;

        static float LineUnits(string line)
        {
            float u = 0f;
            foreach (char c in line) u += c >= 0x1100 ? HangulAdvance : OtherAdvance;
            return u;
        }

        /// <summary>판 크기를 글에서 어림하고 글·기준점·배경을 판 좌표(x 오른쪽, y 위, +z = 보는 사람 반대쪽)에 놓는다.</summary>
        void Layout(string body, int n, int labelLines)
        {
            float glyph = characterSize * fontSize * UnitPerPx;
            float line = glyph * LineSpacing;
            float labelGlyph = labelCharacterSize * fontSize * UnitPerPx;
            float labelLine = labelGlyph * LineSpacing;
            var lines = body.Split('\n');
            float bodyW = 0f;
            foreach (var l in lines) bodyW = Mathf.Max(bodyW, LineUnits(l) * glyph);
            float bodyH = lines.Length * line;
            float col = ColumnWidth(n);
            float scaleW = n * col;
            float scaleH = n > 0 ? line * 0.4f + line + labelLines * labelLine : 0f;
            float w = Mathf.Max(bodyW, scaleW) + 2f * marginM;
            float h = bodyH + scaleH + 2f * marginM;
            PanelSizeM = new Vector2(w, h);

            float top = h * 0.5f - marginM;
            _body.transform.localPosition = new Vector3(0f, top, 0f);
            _body.transform.localRotation = Quaternion.identity;
            float rowTop = top - bodyH - line * 0.4f;
            for (int i = 0; i < n; i++)
            {
                float x = (i - (n - 1) * 0.5f) * col;
                _numbers[i].transform.localPosition = new Vector3(x, rowTop, 0f);
                _numbers[i].transform.localRotation = Quaternion.identity;
                _labels[i].transform.localPosition = new Vector3(x, rowTop - line, 0f);
                _labels[i].transform.localRotation = Quaternion.identity;
            }
            if (_bg != null)
            {
                _bg.transform.localPosition = new Vector3(0f, 0f, 0.01f);   // 글 뒤 1 cm
                _bg.transform.localRotation = Quaternion.identity;
                _bg.transform.localScale = new Vector3(w, h, 1f);
            }
        }

        /// <summary>판 중심을 center에 두고 eye 쪽을 보게 돌린다(앞 +z = 보는 사람 반대쪽, 피치 포함).</summary>
        void Place(Vector3 center, Vector3 eye)
        {
            if (_root == null) return;
            var away = center - eye;
            _root.SetPositionAndRotation(center, away.sqrMagnitude > 1e-6f ? Quaternion.LookRotation(away.normalized, Vector3.up) : Quaternion.identity);
        }

        static void DestroySafe(Object o)
        {
            if (o == null) return;
            if (Application.isPlaying) Destroy(o);
            else DestroyImmediate(o);
        }
    }
}
