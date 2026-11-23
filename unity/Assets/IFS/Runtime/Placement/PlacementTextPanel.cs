// 참여자 안내 패널(배치 실험, 헤드셋 안에서 읽히게): 세계 공간에 고정된 판(머리를 따라다니지 않는다).
//   · 글: TextMesh + OS 동적 폰트(맑은 고딕 등 — ParticipantTextDisplay.EnsureFont와 같은 방식, uGUI·TextMeshPro 없음).
//   · 판: 옅은 회색 사각형(글 뒤 1 cm). 판 전체를 눈 쪽으로 기울여(피치 포함) 글이 눈을 똑바로 보게 한다.
//   · 평정 문항: 문항 글 + 아래에 기준점 줄(문항 범위 min–max, 기본 1–7 — 숫자와 그 아래 기준점 뜻). 참여자 컨트롤러로 고르는 중이면
//     그 칸을 색·굵기·테두리 셋으로 표시한다(색만으로 구별하지 않게 — ui-ux-pro-max §1 color-not-only).
//     칸이 7개보다 많으면(예: 0–10의 11칸) 줄 전체 너비가 7칸 너비를 넘지 않게 칸을 좁힌다. 기준점 뜻은 칸 너비에 맞춰 줄을 바꾼다.
//   · 깊이: 기본 TextMesh 재질(GUI/Text Shader)은 깊이 검사 없이 모든 것 위에 그려져, 판이 물체 뒤에 있어도 글이 물체를 덮는다.
//     그래서 글 재질을 복제해 unity_GUIZTestMode = LessEqual(4)로 둔다(물체가 앞에 있으면 물체가 글을 가린다 — 글이 물체를 가리지 않게).
//   · 색: TextMesh 정점 색은 선형 색공간 프로젝트에서 변환 없이 선형 값으로 쓰인다. Inspector 색(sRGB)이 그대로 보이게
//     선형 색공간이면 Color.linear로 넘긴다(2026-11-23 전에는 짙은 글 #141419가 #4F4F5A로, 고른 숫자가 옅은 파랑 #5AA0ED로 보였음).
// 2026-11-23 G44 화면 개선: 기준점 뜻 글자·숫자 크기(2.24 m에서 잉크 높이 1° 이상), 칸 너비·뜻 줄바꿈(이웃 칸 뜻이 붙어 읽히지 않게),
//   본문 줄 간격 약 1.5 em, 여백, 고른 칸 테두리·바탕, 키가 큰 판(긴 지시문)은 위 가장자리가 maxTopM을 넘지 않게 아래로 내림.
//   수치·계산식은 PlacementPanelMetrics, 실측은 Editor/PlacementUiCapture.cs(docs/validation/ui/). 문구·문항 순서·평정 방식은 그대로.
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
        [SerializeField] int fontSize = PlacementPanelMetrics.FontSize;
        [Tooltip("본문 글자 크기 배율. 0.0085 × fontSize 64 × 0.1 = 글자 칸 5.4 cm(2.24 m에서 한글 잉크 높이 약 1.3°)")]
        [SerializeField] float characterSize = (float)PlacementPanelMetrics.BodyCharacterSize;
        [Tooltip("본문 한 줄 최대 글자 수(띄어쓰기에서 줄을 바꾼다)")]
        [SerializeField] int wrapChars = 20;
        [Tooltip("본문 줄 간격 배율(TextMesh.lineSpacing). 1.13 × 글꼴 줄 높이 1.33 em ≈ 1.5 em")]
        [SerializeField] float bodyLineSpacing = 1.13f;
        [Tooltip("평정 숫자 글자 크기 배율. 0.010이면 숫자 잉크 높이 약 1.2°(2.24 m)")]
        [SerializeField] float numberCharacterSize = (float)PlacementPanelMetrics.NumberCharacterSize;
        [Tooltip("기준점 뜻 글자 크기 배율. 0.0075이면 한글 잉크 높이 약 1.2°(2.24 m)")]
        [SerializeField] float labelCharacterSize = (float)PlacementPanelMetrics.LabelCharacterSize;
        [Tooltip("기준점 뜻 한 줄 최대 글자 수(상한). 실제로는 칸 너비에 들어가는 글자 수와 이 값 중 작은 것")]
        [SerializeField] int labelWrapChars = 6;
        [Tooltip("기준점 한 칸 너비(m)")]
        [SerializeField] float columnWidthM = 0.22f;
        [Tooltip("판 가장자리 여백(m)")]
        [SerializeField] float marginM = 0.08f;
        [SerializeField] Color textColor = new Color(0.08f, 0.08f, 0.1f, 1f);
        [Tooltip("고른 칸의 숫자·뜻 글자색(짙은 파랑, 판 배경·고른 칸 바탕 모두에서 대비 4.5:1 이상)")]
        [SerializeField] Color highlightColor = new Color(0.05f, 0.22f, 0.62f, 1f);
        [SerializeField] Color backgroundColor = new Color(0.90f, 0.90f, 0.91f, 1f);
        [Tooltip("고른 칸 바탕색(판 배경과 구별되는 옅은 파랑)")]
        [SerializeField] Color selectionFillColor = new Color(0.80f, 0.87f, 1.0f, 1f);
        [Tooltip("고른 칸 테두리 두께(m). 0이면 테두리·바탕 없이 색·굵기만")]
        [SerializeField] float selectionFrameM = 0.012f;
        [Tooltip("판(배경) 보이기")]
        [SerializeField] bool showBackground = true;
        [Tooltip("글을 깊이 검사해 물체 뒤에서는 가려지게(끄면 TextMesh 기본: 모든 것 위에 그림)")]
        [SerializeField] bool depthTestText = true;

        [Header("자리")]
        [Tooltip("판 위 가장자리의 최대 높이(m, 바닥 기준). 키가 큰 판(긴 지시문)이 위로 자라 시작 자리 물체 뒤로 들어가지 않게, 넘으면 판을 아래로 내린다. 0 이하면 끔")]
        [SerializeField] float maxTopM = 0.85f;
        [Tooltip("아래로 내릴 때 판 아래 가장자리의 최소 높이(m)")]
        [SerializeField] float minBottomM = 0.05f;

        // 글꼴 단위 → 미터(TextMesh: characterSize × fontSize × 0.1이 대략 한 글자 칸 높이)
        const float UnitPerPx = (float)PlacementPanelMetrics.UnitPerPx;
        const float HangulAdvance = 1.0f, OtherAdvance = 0.55f;
        /// <summary>셀 안쪽 여백(m, 테두리와 글 사이).</summary>
        const float CellPadM = 0.018f;

        Font _font;
        Material _textMat, _bgMat, _selFillMat, _selFrameMat;
        Transform _root;
        TextMesh _body;
        readonly List<TextMesh> _numbers = new List<TextMesh>();
        readonly List<TextMesh> _labels = new List<TextMesh>();
        GameObject _bg, _selFill, _selFrame;
        string _shownKey;
        int _selectedIndex = -1;

        public string CurrentText { get; private set; }
        public bool Visible => _root != null && _root.gameObject.activeSelf;
        /// <summary>마지막으로 그린 판의 크기(m, 너비·높이). 테스트·점검용.</summary>
        public Vector2 PanelSizeM { get; private set; }
        /// <summary>판 중심(세계 좌표).</summary>
        public Vector3 PanelCenter => _root != null ? _root.position : Vector3.zero;
        /// <summary>지금 테두리로 표시한 칸의 값(없으면 null). 테스트·점검용.</summary>
        public int? SelectedValue { get; private set; }

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
            DestroySafe(_selFillMat);
            DestroySafe(_selFrameMat);
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
            string key = "I|" + item.Key + "|" + item.Min + "-" + item.Max + "|" + (cursor?.ToString() ?? "-");
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
                // 조명 방향과 상관없이 밝게(빌드에서 _EMISSION 변형이 빠지면 조명만 받는 회색 판이 된다)
                _bg = MakeQuad("panel background", backgroundColor, 0.6f, ref _bgMat);
            if (selectionFrameM > 0f)
            {
                // 고른 칸: 테두리(짙은 파랑) 위에 바탕(옅은 파랑). 방출 없이 조명만 — 옅은 색이 하얗게 날아가지 않게
                _selFrame = MakeQuad("selected cell frame", highlightColor, 0f, ref _selFrameMat);
                _selFill = MakeQuad("selected cell fill", selectionFillColor, 0f, ref _selFillMat);
                _selFrame.SetActive(false);
                _selFill.SetActive(false);
            }
            _body = MakeText("panel body", characterSize, TextAnchor.UpperCenter);
            _body.lineSpacing = bodyLineSpacing;
            go.SetActive(false);
        }

        GameObject MakeQuad(string name, Color color, float emission, ref Material mat)
        {
            var q = GameObject.CreatePrimitive(PrimitiveType.Quad);
            q.name = name;
            q.transform.SetParent(_root, false);
            var col = q.GetComponent<Collider>();
            if (col != null) DestroySafe(col);
            var r = q.GetComponent<MeshRenderer>();
            if (r != null)
            {
                mat = new Material(r.sharedMaterial) { name = "IFS placement panel " + name };
                mat.color = color;
                if (emission > 0f)
                {
                    mat.EnableKeyword("_EMISSION");
                    mat.SetColor("_EmissionColor", color * emission);
                }
                else mat.SetFloat("_Glossiness", 0f);
                r.sharedMaterial = mat;
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                r.receiveShadows = false;
            }
            return q;
        }

        void Rebuild()
        {
            if (_root == null) return;
            bool was = _root.gameObject.activeSelf;
            DestroySafe(_root.gameObject);
            DestroySafe(_bgMat);
            DestroySafe(_selFillMat);
            DestroySafe(_selFrameMat);
            _bgMat = _selFillMat = _selFrameMat = null;
            _root = null;
            _body = null;
            _numbers.Clear();
            _labels.Clear();
            _bg = _selFill = _selFrame = null;
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
            tm.color = Display(textColor);
            tm.richText = true;
            var r = go.GetComponent<MeshRenderer>();
            if (r != null && mat != null) r.sharedMaterial = mat;
            return tm;
        }

        /// <summary>TextMesh 정점 색으로 넘길 색: 선형 색공간이면 sRGB → 선형(정점 색은 변환되지 않는다).</summary>
        static Color Display(Color c) => QualitySettings.activeColorSpace == ColorSpace.Linear ? c.linear : c;

        float Em(float charSize) => charSize * fontSize * UnitPerPx;

        /// <summary>기준점 줄을 채운다(n = 0이면 숨김). 기준점 뜻의 최대 줄 수를 돌려준다.</summary>
        int SetScale(int n, PlacementItem item, int? cursor)
        {
            while (_numbers.Count < n) _numbers.Add(MakeText("scale number " + _numbers.Count, numberCharacterSize, TextAnchor.UpperCenter));
            while (_labels.Count < n) _labels.Add(MakeText("scale label " + _labels.Count, labelCharacterSize, TextAnchor.UpperCenter));
            int wrap = Mathf.Max(2, Mathf.Min(labelWrapChars, PlacementPanelMetrics.LabelWrapChars(ColumnWidth(n), Em(labelCharacterSize))));
            int maxLines = 0;
            _selectedIndex = -1;
            SelectedValue = null;
            for (int i = 0; i < _numbers.Count; i++)
            {
                bool on = i < n;
                _numbers[i].gameObject.SetActive(on);
                _labels[i].gameObject.SetActive(on);
                if (!on) continue;
                int v = item.Min + i;
                bool sel = PlacementPanelMetrics.IsSelected(cursor, v);
                if (sel) { _selectedIndex = i; SelectedValue = v; }
                _numbers[i].text = sel ? "<b>" + v + "</b>" : v.ToString();
                _numbers[i].color = Display(sel ? highlightColor : textColor);
                string label = ParticipantTextDisplay.Wrap(item.AnchorAt(v) ?? "", wrap);
                _labels[i].text = sel && label.Length > 0 ? "<b>" + label + "</b>" : label;
                _labels[i].color = Display(sel ? highlightColor : textColor);
                maxLines = Mathf.Max(maxLines, label.Length == 0 ? 0 : label.Split('\n').Length);
            }
            return maxLines;
        }

        /// <summary>기준점 한 칸 너비(m): 7칸까지는 columnWidthM, 그보다 많으면 줄 전체가 7칸 너비가 되게 좁힌다.</summary>
        float ColumnWidth(int n) => (float)PlacementPanelMetrics.ColumnWidth(n, columnWidthM);

        static float LineUnits(string line)
        {
            float u = 0f;
            foreach (char c in line) u += c >= 0x1100 ? HangulAdvance : OtherAdvance;
            return u;
        }

        static float MaxLineUnits(string text)
        {
            float m = 0f;
            foreach (var l in (text ?? "").Replace("<b>", "").Replace("</b>", "").Split('\n')) m = Mathf.Max(m, LineUnits(l));
            return m;
        }

        /// <summary>판 크기를 글에서 어림하고 글·기준점·배경을 판 좌표(x 오른쪽, y 위, +z = 보는 사람 반대쪽)에 놓는다.</summary>
        void Layout(string body, int n, int labelLines)
        {
            float glyph = Em(characterSize);
            float bodyPitch = glyph * (float)PlacementPanelMetrics.FontLinePitchEm * bodyLineSpacing;
            float numGlyph = Em(numberCharacterSize);
            float numLine = numGlyph * (float)PlacementPanelMetrics.FontLinePitchEm;
            float labelGlyph = Em(labelCharacterSize);
            float labelPitch = labelGlyph * (float)PlacementPanelMetrics.FontLinePitchEm;
            var lines = body.Split('\n');
            float bodyW = 0f;
            foreach (var l in lines) bodyW = Mathf.Max(bodyW, LineUnits(l) * glyph);
            float bodyH = lines.Length * bodyPitch;
            float col = ColumnWidth(n);
            float gap = n > 0 ? bodyPitch * 0.5f : 0f;
            float cellH = n > 0 ? CellPadM + numLine + labelLines * labelPitch + CellPadM : 0f;
            // 기준점 줄의 가로 범위: 칸 중심 ± max(칸 반폭, 숫자·뜻 반폭) — 양 끝 뜻이 칸보다 넓으면 판을 넓힌다
            float half = 0f;
            for (int i = 0; i < n; i++)
            {
                float x = Mathf.Abs((i - (n - 1) * 0.5f) * col);
                float w = Mathf.Max(MaxLineUnits(_numbers[i].text) * numGlyph, MaxLineUnits(_labels[i].text) * labelGlyph);
                half = Mathf.Max(half, x + Mathf.Max(col * 0.5f, w * 0.5f + CellPadM));
            }
            float w0 = Mathf.Max(bodyW, 2f * half) + 2f * marginM;
            float h = bodyH + gap + cellH + 2f * marginM;
            PanelSizeM = new Vector2(w0, h);

            float top = h * 0.5f - marginM;
            _body.transform.localPosition = new Vector3(0f, top, 0f);
            _body.transform.localRotation = Quaternion.identity;
            float rowTop = top - bodyH - gap;
            for (int i = 0; i < n; i++)
            {
                float x = (i - (n - 1) * 0.5f) * col;
                _numbers[i].transform.localPosition = new Vector3(x, rowTop - CellPadM, 0f);
                _numbers[i].transform.localRotation = Quaternion.identity;
                _labels[i].transform.localPosition = new Vector3(x, rowTop - CellPadM - numLine, 0f);
                _labels[i].transform.localRotation = Quaternion.identity;
            }
            if (_bg != null)
            {
                _bg.transform.localPosition = new Vector3(0f, 0f, 0.01f);   // 글 뒤 1 cm
                _bg.transform.localRotation = Quaternion.identity;
                _bg.transform.localScale = new Vector3(w0, h, 1f);
            }
            bool sel = _selectedIndex >= 0 && _selectedIndex < n && _selFrame != null && _selFill != null;
            if (_selFrame != null) _selFrame.SetActive(sel);
            if (_selFill != null) _selFill.SetActive(sel);
            if (sel)
            {
                // 테두리 상자: 칸 너비(이웃 칸과 띄움), 고른 칸의 숫자·뜻이 더 넓으면 그만큼
                int i = _selectedIndex;
                float x = (i - (n - 1) * 0.5f) * col;
                float textW = Mathf.Max(MaxLineUnits(_numbers[i].text) * numGlyph, MaxLineUnits(_labels[i].text) * labelGlyph);
                float boxW = Mathf.Max(col - 0.012f, textW + 2f * CellPadM);
                float y = rowTop - cellH * 0.5f;
                _selFrame.transform.localPosition = new Vector3(x, y, 0.006f);   // 바탕보다 뒤, 판 배경보다 앞
                _selFrame.transform.localRotation = Quaternion.identity;
                _selFrame.transform.localScale = new Vector3(boxW, cellH, 1f);
                _selFill.transform.localPosition = new Vector3(x, y, 0.003f);
                _selFill.transform.localRotation = Quaternion.identity;
                _selFill.transform.localScale = new Vector3(Mathf.Max(0.001f, boxW - 2f * selectionFrameM), Mathf.Max(0.001f, cellH - 2f * selectionFrameM), 1f);
            }
        }

        /// <summary>판 중심을 center에 두고 eye 쪽을 보게 돌린다(앞 +z = 보는 사람 반대쪽, 피치 포함).
        /// 판 위 가장자리가 maxTopM보다 높으면(긴 지시문처럼 키가 큰 판) 아래 가장자리가 minBottomM에 닿을 때까지 중심을 내린다.</summary>
        void Place(Vector3 center, Vector3 eye)
        {
            if (_root == null) return;
            var c = center;
            if (maxTopM > 0f)
            {
                float halfUp = PanelSizeM.y * 0.5f * Mathf.Abs((LookAt(c, eye) * Vector3.up).y);
                if (c.y + halfUp > maxTopM) c.y = Mathf.Max(maxTopM - halfUp, minBottomM + halfUp);
            }
            _root.SetPositionAndRotation(c, LookAt(c, eye));
        }

        static Quaternion LookAt(Vector3 center, Vector3 eye)
        {
            var away = center - eye;
            return away.sqrMagnitude > 1e-6f ? Quaternion.LookRotation(away.normalized, Vector3.up) : Quaternion.identity;
        }

        static void DestroySafe(Object o)
        {
            if (o == null) return;
            if (Application.isPlaying) Destroy(o);
            else DestroyImmediate(o);
        }
    }
}
