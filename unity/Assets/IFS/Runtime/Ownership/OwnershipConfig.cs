// 소유감 실험 설정(설계 1.9). 값과 generatorVersion을 manifest.json의 config에 그대로 남긴다.
// UnityEngine에 의존하지 않는다. Inspector에서 바꿀 수 있다(바꾸면 결정 기록에 남길 것).
using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec.Ownership
{
    [Serializable]
    public sealed class OwnershipConfig
    {
        /// <summary>0.2: 색 ΔE00을 셰이더 알베도(밝기 배율) 기준으로, 합성 ΔE00 기록, 흔들림 + 구는 자세가 none일 때만 보이지 않음.
        /// 0.3: 같은 말·다른 값 쌍(color_lo·color_hi·size_lo·size_hi), 변형 kind, 보여 줄 조건을 정한 뒤 n조건 Williams 순서.
        /// shiftAttributes가 비면 변형·순서는 0.2와 같다.</summary>
        public const string GeneratorVersion = "ownership-variants/0.3";

        /// <summary>같은 말·다른 값 쌍을 만들 수 있는 속성(정해진 순서).</summary>
        public static readonly string[] ShiftAttributeNames = { "color", "size" };
        public const string RatingResemblance = "resemblance";
        public const string RatingMine = "mine";
        /// <summary>어긋난 변형까지의 조건 수(orig + form·color·size·motion).</summary>
        public const int BaseConditionCount = 5;

        /// <summary>layout.size(로그 척도) 변화량. 0.25 = 지름 ×2 또는 ÷2. (0, 0.5]</summary>
        public double sizeStep = 0.25;
        /// <summary>색 변형 목표 CIEDE2000(잠정값).</summary>
        public double colorDeltaE = 30;
        /// <summary>형상 하나를 보여 주는 시간(초).</summary>
        public double viewSeconds = 30;
        /// <summary>머리 자세 기록 빈도(Hz).</summary>
        public double headSampleHz = 20;
        /// <summary>분석의 응시 원뿔 반각(도). 기록에는 각도 원값을 쓰고 이 값은 분석 참고용.</summary>
        public double gazeConeDeg = 15;
        /// <summary>마지막 선택에서 5개를 놓는 호의 전체 각(도). 위치 1이 왼쪽 끝.</summary>
        public double finalChoiceArcDeg = 120;
        /// <summary>마지막 선택·차이 평정에서 머리–형상 수평 거리(m). 0이면 원본의 layout.distance로 놓은 거리.</summary>
        public double finalChoiceRadiusM = 0;
        /// <summary>평정·선택 뒤 "원본과 얼마나 다른가" 평정(조작 크기 점검).</summary>
        public bool differenceRating = true;
        /// <summary>켜면 문구 파일에 status draft 문구가 하나라도 있을 때 세션 시작을 거부한다(IRB 확인 뒤 본 실험용). 기본 꺼짐.</summary>
        public bool requireSpecPhrases = false;

        // ── 같은 말·다른 값 쌍(값은 모두 잠정) ──
        /// <summary>쌍을 만들 속성(color·size). 빈 목록이면 0.2와 똑같이 원본 + 어긋난 변형 4개만.</summary>
        public List<string> shiftAttributes = new List<string> { "color", "size" };
        /// <summary>쌍의 layout.size(로그 척도) 이동폭(잠정). (0, 0.5]</summary>
        public double sizeShiftStep = 0.10;
        /// <summary>색 쌍의 목표 CIEDE2000(셰이더 알베도 기준, 잠정).</summary>
        public double colorShiftDeltaE = 12;
        /// <summary>유채색 쌍에서 색상을 돌리는 최대 각(도, 잠정). 어휘에 색 낱말의 범위가 없어 좁게 둔다. [1, 180]</summary>
        public double maxHueShiftDeg = 20;
        /// <summary>색 쌍의 |ΔE00(lo) − ΔE00(hi)| 허용치(잠정). 넘으면 asymmetric으로 둘 다 보이지 않는다.</summary>
        public double shiftSymmetryTolerance = 3;
        /// <summary>형상마다 받는 평정 문항: resemblance(떠올린 모습과 닮았다, 기본) | mine(내 것 같다).</summary>
        public string ratingItem = RatingResemblance;

        public OwnershipConfig Clone()
        {
            var c = (OwnershipConfig)MemberwiseClone();
            c.shiftAttributes = shiftAttributes != null ? new List<string>(shiftAttributes) : null;
            return c;
        }

        /// <summary>켜진 쌍 속성(정해진 순서, 중복 없음).</summary>
        public List<string> EnabledShiftAttributes()
        {
            var on = new List<string>();
            foreach (var a in ShiftAttributeNames)
                if (shiftAttributes != null && shiftAttributes.Contains(a)) on.Add(a);
            return on;
        }

        public List<string> Validate()
        {
            var e = new List<string>();
            if (!(sizeStep > 0 && sizeStep <= 0.5)) e.Add($"sizeStep {sizeStep}: (0, 0.5] 밖");
            if (!(colorDeltaE > 0)) e.Add($"colorDeltaE {colorDeltaE}: 0보다 커야 함");
            if (!(viewSeconds > 0)) e.Add($"viewSeconds {viewSeconds}: 0보다 커야 함");
            if (!(headSampleHz > 0 && headSampleHz <= 200)) e.Add($"headSampleHz {headSampleHz}: (0, 200] 밖");
            if (!(gazeConeDeg > 0 && gazeConeDeg < 180)) e.Add($"gazeConeDeg {gazeConeDeg}: (0, 180) 밖");
            if (!(finalChoiceArcDeg > 0 && finalChoiceArcDeg <= 180)) e.Add($"finalChoiceArcDeg {finalChoiceArcDeg}: (0, 180] 밖");
            if (!(finalChoiceRadiusM >= 0)) e.Add($"finalChoiceRadiusM {finalChoiceRadiusM}: 0 이상이어야 함");
            if (shiftAttributes == null) e.Add("shiftAttributes: null(끄려면 빈 목록)");
            else
            {
                foreach (var a in shiftAttributes)
                    if (Array.IndexOf(ShiftAttributeNames, a) < 0) e.Add($"shiftAttributes: 모르는 속성 '{a}'(color·size만)");
                if (new HashSet<string>(shiftAttributes).Count != shiftAttributes.Count) e.Add("shiftAttributes: 같은 속성이 두 번");
                int max = BaseConditionCount + 2 * EnabledShiftAttributes().Count;
                if (max > WilliamsDesign.MaxConditions)
                    e.Add($"조건이 최대 {max}개가 될 수 있음: 마지막 선택 키(1–{WilliamsDesign.MaxConditions})로 받을 수 없음");
            }
            if (!(sizeShiftStep > 0 && sizeShiftStep <= 0.5)) e.Add($"sizeShiftStep {sizeShiftStep}: (0, 0.5] 밖");
            if (!(colorShiftDeltaE > 0)) e.Add($"colorShiftDeltaE {colorShiftDeltaE}: 0보다 커야 함");
            if (!(maxHueShiftDeg >= 1 && maxHueShiftDeg <= 180)) e.Add($"maxHueShiftDeg {maxHueShiftDeg}: [1, 180] 밖");
            if (!(shiftSymmetryTolerance >= 0)) e.Add($"shiftSymmetryTolerance {shiftSymmetryTolerance}: 0 이상이어야 함");
            if (ratingItem != RatingResemblance && ratingItem != RatingMine) e.Add($"ratingItem '{ratingItem}': resemblance 또는 mine");
            return e;
        }

        public JObject ToJson() => new JObject
        {
            ["generatorVersion"] = GeneratorVersion,
            ["sizeStep"] = sizeStep,
            ["colorDeltaE"] = colorDeltaE,
            ["viewSeconds"] = viewSeconds,
            ["headSampleHz"] = headSampleHz,
            ["gazeConeDeg"] = gazeConeDeg,
            ["finalChoiceArcDeg"] = finalChoiceArcDeg,
            ["finalChoiceRadiusM"] = finalChoiceRadiusM,
            ["differenceRating"] = differenceRating,
            ["requireSpecPhrases"] = requireSpecPhrases,
            ["shiftAttributes"] = new JArray((shiftAttributes ?? new List<string>()).ToArray()),
            ["sizeShiftStep"] = sizeShiftStep,
            ["colorShiftDeltaE"] = colorShiftDeltaE,
            ["maxHueShiftDeg"] = maxHueShiftDeg,
            ["shiftSymmetryTolerance"] = shiftSymmetryTolerance,
            ["ratingItem"] = ratingItem,
        };
    }
}
