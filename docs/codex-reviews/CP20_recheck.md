## 지적 3건 상태

| 지적 | 상태 | 근거 |
|---|---|---|
| 근거 낱말은 모든 분기에서 확정 텍스트의 부분 구간인가? 구간 불일치 때 LLM 없는 경로로 가는가? | **고쳐짐** | `<repo>/chatbot/ifs_chatbot/llm_shape.py:446-467`에서 인용과 구간이 정확히 맞는지 먼저 확인하고, 불일치하면 `shownText`와 `text`를 비웁니다. 맞으면 화면 낱말과 `shownSpan`을 원문에서 가져오며 `<repo>/chatbot/ifs_chatbot/llm_shape.py:503`에서 부분 구간임을 단언합니다. `<repo>/chatbot/ifs_chatbot/selection.py:1092-1102`는 근거를 표시할 수 없을 때 `route=none`으로 돌리고, `:320-323`은 그 경로에서 형태 후보를 내보내지 않습니다. |
| 반복 멈춤 단계에서 XR 연결이 끊긴 동안 멈추고 재연결 후 이어지는가? 새 경계 상황에서 방향·속도 문제는 없는가? | **일부** | `<repo>/unity/Assets/IFS/Runtime/Placement/PlacementSession.cs:1288-1313`은 끊긴 프레임의 입력을 버리고 라운드 제한 시간 또는 라운드 사이 간격을 보정하며, 재연결 후 입력을 버린 다음 진행합니다. 라운드 안에서는 이동 방향과 정지 상태를 보존합니다(`<repo>/unity/Assets/IFS/Runtime/Placement/PlacementSession.cs:1317-1329`, `:1351-1369`). 다만 끊긴 동안 실험자가 단계를 넘길 때의 처리는 시험 근거가 없고, 구현에서도 XR 복귀 때까지 그 단계 전환을 막는 처리는 보이지 않습니다. 라운드 사이 끊김은 간격을 늘리는 방식이라 다음 라운드가 늦게 시작됩니다. |
| 추가 시험이 지적을 실제로 고정하는가? | **일부** | 근거 구간 시험은 문구 두 종류에서 일치하지 않는 구간, 누락·범위 초과·불리언 오프셋을 검사하고, 불일치 항목이 LLM 없는 경로로 가는 것도 확인합니다(`<repo>/chatbot/tests/test_g83_g82_on.py:102-135`). XR 시험은 라운드 도중 장시간 끊겼을 때 시간·물체·입력이 멈추고 재연결 뒤 진행되는지 검사합니다(`<repo>/unity/Assets/IFS/Tests/Editor/PlacementStopLoopTests.cs:280-351`). 하지만 단계 넘김, 라운드 사이 끊김, 멈춘 상태에서 끊겼다 돌아오는 경우를 별도로 고정하는 시험은 확인되지 않았습니다. |

## 새로 찾은 문제

- **중간 — XR 복귀 직후 첫 입력 프레임의 이동 시간이 과대 반영될 수 있음.** 복귀 프레임은 입력을 버리지만, 이동 계산에는 그 프레임의 `dt`를 그대로 씁니다(`<repo>/unity/Assets/IFS/Runtime/Placement/PlacementSession.cs:1301-1308`, `:1317-1329`). 프레임 정지나 큰 `dt`가 동반되면 재연결 직후 물체가 예상보다 멀리 움직이거나 경계 반사가 달라질 수 있습니다. 기존 시험은 일정한 20ms 프레임만 사용합니다(`<repo>/unity/Assets/IFS/Tests/Editor/PlacementStopLoopTests.cs:291-292`).

- **낮음 — 작업 트리에 커밋되지 않은 XR 설정 변경이 있습니다.** `git status --short`에서 `unity/Assets/XR/Settings/OpenXRPackageSettings.asset`이 수정된 것으로 나타났습니다. 마지막 커밋 검토 범위 밖의 변경입니다.