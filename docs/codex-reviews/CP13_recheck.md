**1–4번 지적은 모두 고쳐졌습니다.** 확인은 `b6e1f6c`의 구현과 테스트를 기준으로 했으며, 새 전면 검토는 하지 않았습니다.

1. **고쳐짐** — [none_gen.py](<repo>/chatbot/ifs_chatbot/none_gen.py:297)  
   Ollama 내림 요청 결과와 `/api/ps` 잔류 여부를 확인합니다. 내림이 실패하거나 모델이 남아 있으면 생성 프로세스를 실행하지 않고 차단합니다.

2. **고쳐짐** — [controller.py](<repo>/chatbot/ifs_chatbot/controller.py:310), [none_gen.py](<repo>/chatbot/ifs_chatbot/none_gen.py:155)  
   세션 생성·시작·답변 등 면담 요청을 생성 작업과 조정하고, 재적재 실패 시 `guard.required` 설정에서 새 세션을 막으며 백그라운드 재시도를 합니다.

3. **고쳐짐** — [none_gen.py](<repo>/chatbot/ifs_chatbot/none_gen.py:434)  
   앞 작업이 재적재 중이면 다음 작업은 예약된 채 `released`를 기다린 뒤 시작합니다.

4. **고쳐짐** — [selection.py](<repo>/chatbot/ifs_chatbot/selection.py:629), [none_gen.py](<repo>/chatbot/ifs_chatbot/none_gen.py:133)  
   건너뛰기 상태와 응답을 먼저 처리하고, 프로세스 종료는 데몬 스레드에서 수행합니다.

**5. 이번 수정으로 새로 생긴 높음·중간 문제**

- **키워드 위기 고정 문구 경로가 409에 막히지는 않습니다.** `reply()`가 면담 슬롯에 진입할 때 위기 키워드를 판별해 `crisis_ok`로 허용하고, CP12 동작에 따라 가드 모델 호출 없이 고정 문구 분기로 갑니다([controller.py](<repo>/chatbot/ifs_chatbot/controller.py:310), [controller.py](<repo>/chatbot/ifs_chatbot/controller.py:432)). 다만 **`action=edit`에 위기 문구를 보낸 경우** `act()`가 이를 면담 슬롯 진입 전에 키워드 예외로 분류하지 않아 409가 날 수 있습니다([controller.py](<repo>/chatbot/ifs_chatbot/controller.py:489), [controller.py](<repo>/chatbot/controller.py:523)). 편집 확정은 답변 제출과 다른 경로이므로, 위기 고정 문구 보장 범위가 편집까지라면 **새 중간 문제**입니다.
- **잠금 교착은 확인되지 않았습니다.** 면담 슬롯 잠금은 짧은 상태 확인·예약 구간이고, 세션 잠금과 겹쳐도 역순으로 잠금을 잡고 기다리는 경로는 확인되지 않았습니다.
- **재시도 스레드가 서버 종료를 막지는 않습니다.** 재시도는 `daemon=True`이고 종료 시 `_closed`를 설정합니다([none_gen.py](<repo>/chatbot/ifs_chatbot/none_gen.py:370), [none_gen.py](<repo>/chatbot/ifs_chatbot/none_gen.py:615)).
- **다른 설정으로의 영향은 제한되어 있습니다.** `on_none`이 꺼져 있으면 `none_gen`이 없어 기존 면담 슬롯은 무동작이며, 재적재 실패로 인한 세션 차단도 `guard.required`일 때만 적용됩니다([controller.py](<repo>/chatbot/ifs_chatbot/controller.py:217), [none_gen.py](<repo>/chatbot/ifs_chatbot/none_gen.py:405)). **단, 생성 중인 기존 세션의 별도 `act` 경로에서 면담 입력 차단이 일관적인지는 이번 확인 범위를 넘어 추가로 단정하지 않습니다.**