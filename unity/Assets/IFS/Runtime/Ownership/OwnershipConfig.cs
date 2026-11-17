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
        public const string GeneratorVersion = "ownership-variants/0.1";

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

        public OwnershipConfig Clone() => (OwnershipConfig)MemberwiseClone();

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
        };
    }
}
