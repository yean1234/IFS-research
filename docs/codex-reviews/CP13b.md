## 지적

1. **[중간] 제한 시간이 파이프라인 초기화를 포함하지 않습니다.**  
   파일: [resay_flow.py](<repo>/chatbot/ifs_chatbot/resay_flow.py:359), [resay_flow.py](<repo>/chatbot/ifs_chatbot/resay_flow.py:363)  
   재현: 첫 제출에서 `ResayService.pipeline`이 Kiwi/매퍼를 초기화하는 동안 지연되면, `started`와 `deadline`은 초기화가 끝난 뒤에야 설정됩니다. 따라서 G73-d의 제출부터 회차 종료까지 제한 시간이 초기화 지연만큼 늘어납니다.  
   수정: 제출 시각을 먼저 기록하고 제한 시간을 시작한 뒤 초기화·매핑·생성 전체를 그 안에서 수행하거나, 초기화도 제한 시간에 포함되도록 바꾸세요.

2. **[중간] 값이 기존 값과 같으면 `resaid` 출처가 빠집니다.**  
   파일: [resay_flow.py](<repo>/chatbot/ifs_chatbot/resay_flow.py:632), [resay_flow.py](<repo>/chatbot/ifs_chatbot/resay_flow.py:733)  
   재현: 확정 스펙의 `form.type`이 이미 `mist`인 세션에서 다시 적은 글도 `mist` 갈래로 판정되면, 덮어쓰기 값은 적용되지만 `slotsChanged`가 비어 있습니다. 이후 `sourceDetails.form.type`은 `resaid`가 아니라 기존 `said`로 남습니다. G73-e의 값 출처 기록과 어긋납니다.  
   수정: 출처 판정은 값 변경 여부와 분리하고, 실제 적용된 재진술 슬롯을 기록해 값이 같아도 그 출처를 보존하세요.

3. **[중간] 철회해도 진행 중 생성 작업을 취소하지 않습니다.**  
   파일: [controller.py](<repo>/chatbot/ifs_chatbot/controller.py:512), [controller.py](<repo>/chatbot/ifs_chatbot/controller.py:521)  
   재현: 생성 대기 중 `withdraw()`를 호출하면 선택 기록은 삭제되고 흐름 참조도 끊기지만, `ResayState.token`은 무효화되지 않고 `cancel`도 설정되지 않습니다. 이미 시작한 생성 작업은 계속 실행될 수 있습니다.  
   수정: 철회·세션 종료 시 재진술 작업을 취소하고 토큰을 무효화하세요. 서버 종료 경로에도 같은 정리를 연결하세요.

4. **[낮음] 조건 간 흐름 동등성 시험이 종료·실패 경로까지 다루지 않습니다.**  
   파일: [test_g73_resay_flow.py](<repo>/chatbot/tests/test_g73_resay_flow.py:517)  
   재현: 현재 두 조건 비교는 `solid`, `mist`, `blocked` 입력만 검사합니다. 위기, 건너뛰기, 제한 시간 초과, 생성 실패, 회차 상한에서 static·chatbot 조건의 기록·기준 후보 복귀가 같은지는 확인하지 않습니다.  
   수정: 해당 종료 경로를 조건별로 비교하고, 제출→초기화 지연이 제한 시간에 포함되는지도 시험하세요.