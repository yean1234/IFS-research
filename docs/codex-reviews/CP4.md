# CP4 — 후보1 프로토타입 검토 (Codex 독립 검토)

- 일시: 2026-11-17
- 호출: `codex exec --sandbox read-only -c model_reasoning_effort="medium"` (후보1 프로토타입 작업 2/3회)
- 프롬프트: `docs/codex-reviews/prompts/CP4_prompt.md`
- 판정(수용/반박/보류)은 `docs/decisions.md`에 적습니다.

---

1. **[심각도: 높음] 응시 시간 계산이 표본 누락을 반영하지 않습니다.** 위치: [OwnershipRunner.cs](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipRunner.cs:736), [ownership.py](<repo>/chatbot/ifs_chatbot/eval/ownership.py:193)  
   `Tick`이 밀리면 러너는 현재 머리 자세를 과거 시각 표본 여러 개에 기록하고, 10개를 넘게 밀리면 표본을 건너뜁니다. 분석기는 실제 시각 간격과 관계없이 각 표본을 `1000 / headSampleHz`만큼 응시한 것으로 셉니다. 프레임 지연 시 자세 경로가 복제되고 응시 시간이 과대 계산될 수 있습니다.  
   **제안:** 실제 표본 시각 차이를 사용해 응시 시간을 적분하고, 긴 간격을 구간으로 처리하거나 해당 구간을 결측으로 표시하십시오. catch-up 표본에는 같은 프레임의 자세를 반복 기록하지 않도록 하십시오.

2. **[심각도: 중간] Williams 순서 배정이 참가자 번호에 고정되어 있습니다.** 위치: [WilliamsDesign.cs](<repo>/unity/Assets/IFS/Runtime/Ownership/WilliamsDesign.cs:25)  
   `RowFor`와 `CbFor`는 참가자 번호만으로 순서 행과 균형 비트를 정합니다. 번호를 건너뛰거나 재사용하거나 편의상 배정하면 조건 순서가 모집 순서와 결합되어 균형이 깨질 수 있습니다. 예컨대 참가자 번호가 1, 3, 5로만 배정되면 Williams 10개 행 중 일부만 반복됩니다.  
   **제안:** 참가자 등록 시 순서 행을 별도로 배정·기록하고, 실제 배정 수를 점검하십시오.

3. **[심각도: 중간] `first_look_ms`는 형상 제시 시점이 아니라 첫 기록 표본부터 잽니다.** 위치: [ownership.py](<repo>/chatbot/ifs_chatbot/eval/ownership.py:202)  
   `t0 = samples[0]["t"]`를 기준으로 첫 응시 시간을 계산합니다. 첫 viewing 표본이 제시 시작보다 늦으면 그 지연이 빠져 응시 시작 시간이 실제보다 짧게 나옵니다. 현재 문서도 이 정의를 명시하지만, 지표 이름과 연구 질문의 “평정 전 행동” 해석에는 제시 시점 기준이 더 직접적입니다.  
   **제안:** 제시 시작 시각을 기록해 그 시각을 기준으로 계산하거나, 현재 방식의 지표명을 “첫 표본 이후 첫 응시”로 명확히 바꾸십시오.

4. **[심각도: 중간] SpecCheck의 ‘말한 값’ 표시는 provenance 존재 여부와 일치하지 않을 수 있습니다.** 위치: [OwnershipRunner.cs](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipRunner.cs:827)  
   화면 표시는 슬롯 값이 null인지로 stated/default를 나눕니다. 값은 있으나 해당 슬롯의 provenance가 없거나 불완전한 spec이면 stated로 보이지만, 생성기는 provenance 유무로 `source`를 정합니다. 따라서 실험자가 화면에서 확인한 출처와 분석에 쓰이는 출처가 달라질 수 있습니다.  
   **제안:** 화면 라벨도 provenance 기준으로 산출하고, 값은 있지만 provenance가 없는 경우는 미확인으로 표시하십시오.

5. **[심각도: 낮음] `first_look_ms`의 시작점과 표본 누락에 관한 검증이 부족합니다.** 위치: [test_ownership_eval.py](<repo>/chatbot/tests/test_ownership_eval.py:78)  
   현재 수기 계산 테스트는 일정한 50ms 표본 간격만 검사합니다. 불규칙 간격·장시간 누락·제시 시작과 첫 표본 사이 지연 사례가 없어, 위 시간 지표의 한계가 테스트에서 드러나지 않습니다.  
   **제안:** 지연·누락이 포함된 합성 표본으로 응시 시간과 첫 응시 시각 계산을 고정하는 테스트를 추가하십시오.

총평: 기록 열과 분석기의 기본 필드 대응은 대체로 일관됩니다.  
주요 분석 위험은 프레임 지연 시 응시 시간·머리 경로가 왜곡될 수 있다는 점입니다.  
순서 배정은 참가자 번호에 의존하므로 실제 모집·재시작 방식에서 균형이 유지되는지 확인이 필요합니다.