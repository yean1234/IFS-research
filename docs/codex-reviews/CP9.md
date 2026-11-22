# CP9 — 실험 프로토타입 구현 검토 (Codex 독립 검토)

- 일시: 2026-11-23
- 호출: `codex exec --sandbox read-only -c model_reasoning_effort="medium"` (사용량 한도 사용률 2%)
- 프롬프트: `docs/codex-reviews/prompts/CP9_prompt.md`
- 검토 대상 커밋: `acdfd28..1051d48`
- 판정은 `docs/decisions.md` G26–G28에 적습니다.

---

1. **[심각도: 높음]** 위치: [chatbot/ifs_chatbot/selection.py:201](<repo>/chatbot/ifs_chatbot/selection.py:201), [unity/Assets/IFS/Runtime/Placement/PlacementRunner.cs:295](<repo>/unity/Assets/IFS/Runtime/Placement/PlacementRunner.cs:295), [shared/schemas/selection.v0.1.json:63](<repo>/shared/schemas/selection.v0.1.json:63)  
   **문제:** spec 파일이 없는 실행에서 `specSha256`은 `spec_dumps()`로 직렬화한 텍스트의 해시가 됩니다. 러너는 `sha256Basis`를 확인하지 않고, 사용자가 저장한 spec 파일의 바이트 해시와 무조건 비교합니다.  
   **근거:** `persist_logs=False`이거나 spec 경로가 없으면 `sha256Basis="serialized"`로 기록하지만, Unity의 `SpecMismatch()`는 직렬화 기준을 처리하지 않습니다. 이 경로에서 반환된 선택 파일과 spec을 저장해 러너에 넣으면 같은 spec 내용이어도 바이트 표현이 다를 때 시작을 거부할 수 있습니다.  
   **제안:** 러너가 `serialized` 기준을 명시적으로 처리하거나, 러너 입력용 spec 파일을 먼저 확정해 그 파일 바이트 해시만 선택 파일에 기록하게 계약을 좁히세요.

2. **[심각도: 중간]** 위치: [unity/Assets/IFS/Runtime/Placement/PlacementSelection.cs:136](<repo>/unity/Assets/IFS/Runtime/Placement/PlacementSelection.cs:136), [shared/schemas/selection.v0.1.json:144](<repo>/shared/schemas/selection.v0.1.json:144)  
   **문제:** JSON 스키마는 `sources` 값이 `said|chosen|edited|default` 중 하나여야 한다고 제한하지만, 러너는 객체를 그대로 복사하고 값과 슬롯 키를 검증하지 않습니다. 잘못되거나 오타 난 출처가 분석 기록까지 들어갈 수 있습니다.  
   **근거:** 임의의 `sources: {"layout.size":"chosne"}`가 있어도 선택 파일 파싱 단계에서 오류가 되지 않습니다.  
   **제안:** 스키마와 같은 슬롯명·출처 enum 검증을 러너에도 추가하고, 잘못된 값은 시작 오류로 처리하세요.

3. **[심각도: 중간]** 위치: [chatbot/ifs_chatbot/candidates.py:208](<repo>/chatbot/ifs_chatbot/candidates.py:208), [chatbot/ifs_chatbot/candidates.py:160](<repo>/chatbot/ifs_chatbot/candidates.py:160)  
   **문제:** G8의 같은 spec에 대한 후보 결과는 같지만, 반환 객체의 `displayOrder`는 세션 ID에 따라 달라집니다. G20이 화면 순서를 세션 ID로 순환시키도록 정했으므로 순환 자체는 의도된 동작이나, “같은 확정 텍스트 → 같은 spec → 같은 후보·같은 표시 순서”를 세션과 무관한 재현 기준으로 삼으면 성립하지 않습니다.  
   **근거:** 같은 spec을 서로 다른 세션 ID로 `generate()`에 넣으면 후보 ID는 같고 순환된 표시 순서는 달라질 수 있습니다. `selection.json`은 실제 표시 순서를 기록합니다.  
   **제안:** 검증 기준을 “같은 spec과 같은 sessionId에서 같은 표시 순서”로 명시하고, 세션 간 재현이 필요하면 생성된 후보 순서와 표시 순서를 구분해 비교하세요.

총평: 확인된 계약상 위험은 직렬화 해시 기준과 러너의 출처 값 검증 누락입니다.  
G8 후보 결정성과 G20 세션별 순환은 구분해서 검증해야 합니다.  
그 외 항목은 이번 검토에서 결정·원칙과 어긋나는 재현 가능한 결함으로 확정하지 않았습니다.
