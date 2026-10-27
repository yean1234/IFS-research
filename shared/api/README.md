# 면담 서버 HTTP API (v0.1)

웹 데모(`chatbot/ifs_chatbot/web`)와 Unity가 같은 API를 씁니다. 서버는 기본으로 `http://127.0.0.1:8000`에만 열립니다.
본문은 모두 UTF-8 JSON입니다. FastAPI가 만든 대화형 문서는 서버를 켠 뒤 `/docs`에서 볼 수 있습니다.

## 엔드포인트

| 메서드 · 경로 | 본문 | 돌려주는 것 | 쓰임 |
| --- | --- | --- | --- |
| `GET /api/health` | — | 모델·가드·사전·프롬프트 버전, 경고 | 시작 화면, 상태 표시 |
| `GET /api/protocol` | — | `shared/protocol/elicitation_protocol.v1.json` 전체 | Unity가 VR 단계 고정 문구를 같은 출처에서 읽기 |
| `POST /api/sessions` | `{"condition": "chatbot"\|"static", "sessionId": "P07"}` | 세션 화면(아래) · 201 | 세션 만들기. ID를 비우면 자동 생성 |
| `GET /api/sessions` | — | 세션 목록 | 연구자 화면 |
| `GET /api/sessions/{id}` | — | 세션 화면 | 다시 그리기 |
| `POST /api/sessions/{id}/start` | — | 세션 화면 | 안내 뒤 [시작] |
| `POST /api/sessions/{id}/reply` | `{"text": "가슴이 좀 답답해요"}` | 세션 화면 | 참여자 답 (최대 2,000자) |
| `POST /api/sessions/{id}/action` | `{"action": "...", "text": "..."}` | 세션 화면 | 버튼: `start` `skip` `continue` `stop` `confirm` `edit` `withdraw` |
| `GET /api/sessions/{id}/log` | — | `{"session", "log", "runtimeWarnings"}` | 연구자 화면. `log`는 elicit-log/0.1 |
| `POST /api/sessions/{id}/events` | `{"type": "calibration", "payload": {...}}` | 기록된 이벤트 · 201 | VR 쪽 기록을 같은 세션 로그에 묶기 |
| `POST /api/guard/check` | `{"text": "..."}` | 안전 판정 + 낼 고정 문구 | VR 단계(Feel toward 등) 발화도 같은 L1 검사 |

오류: 순서가 틀린 요청(예: 시작 전에 답 보내기)은 `409`, 없는 세션은 `404`. 본문은 `{"detail": "사유"}`입니다.

## 세션 화면 (view)

```json
{
  "sessionId": "P07",
  "condition": {"id": "chatbot", "label": "조건 2 · AI 챗봇 면담"},
  "state": "interview",
  "awaiting": "reply",
  "stage": "find",
  "stageInfo": {"ifs": "Find", "labelKo": "찾기", "purposeKo": "참여자가 처음 알아차린 것(…)과 그것이 몸 안·표면·주변 중 어디에 있는지를 찾는다."},
  "messages": [
    {"speaker": "participant", "text": "가슴이 좀 답답해요", "i": 3},
    {"speaker": "bot", "text": "그것이 몸 안에, 몸 표면에, 아니면 몸 주변에 있나요?", "kind": "question", "source": "fixed:location", "i": 4}
  ],
  "buttons": [{"action": "skip", "label": "넘어가기"}, {"action": "stop", "label": "그만"}],
  "confirmDraft": null,
  "progress": {"step": 1, "steps": 8, "llmTurns": 0}
}
```

- `state`: `intro` `interview` `soft_check` `confirm` `done` `stopped` `crisis` `withdrawn`
- `awaiting`: 지금 받을 입력. `start` `reply` `soft_check` `confirm` `none`
- `messages[].kind`: `question` `info` `check`(확인 문구) `crisis` `confirm` `closing`. VR에서는 `kind`로 음성·화면 연출을 바꿀 수 있습니다.
- `messages[].source`: `fixed:<문구 id>`이면 고정 문구, `llm`이면 검증을 통과한 LLM 질문.
- `buttons`: 지금 누를 수 있는 동작. 손바닥 펴기 제스처는 `stop`, 상자 닫기 이후 종료는 Unity 쪽 흐름입니다.
- `confirmDraft`: `awaiting`이 `confirm`일 때 보여 줄 확정 텍스트(참여자 말을 그대로 모은 것).

## 안전 검사 (VR 단계용)

```json
POST /api/guard/check   {"text": "숨이 막히는 느낌이 올라와요"}
→ {"level": "soft", "label": "controversial", "alert": false,
   "reasons": ["kw:metaphor:cannot_breathe"], "keywordHits": [{"tier": "metaphor", "id": "cannot_breathe", "match": "숨이 막히", "span": [0, 5]}],
   "model": null, "softCheckPhrase": "지금 계속 이야기해도 괜찮으신가요?", "crisisPhrase": null}
```

- `level`이 `soft`면 `softCheckPhrase`를 띄우고 [계속][그만]을 받습니다(스토리보드 13′).
- `crisis`면 LLM·VR 연출을 멈추고 `crisisPhrase`(109 · 1577-0199 · 연구자 연락처)를 보여 주고 연구자를 부릅니다.
- `model`에는 가드 모델 판정이 들어갑니다. 가드 모델이 없으면 `null`이고 키워드 사전만으로 판정합니다.

## VR 이벤트 묶기

Unity가 따로 남기는 `initialScene.json`, `finalScene.json`, `events.csv`(거리 0.1초 간격)와 별도로, 요약값을 같은 세션 로그에 붙일 수 있습니다.

```json
POST /api/sessions/P07/events
{"type": "calibration", "payload": {"scaleDelta": -0.25, "glossDelta": 0.4, "yDelta": -0.2, "seconds": 100}}
{"type": "distance_summary", "payload": {"nearestM": 2.5, "voluntaryApproaches": 1, "dwellSeconds": 20}}
{"type": "feel_toward", "payload": {"text": "좀 짜증나요", "guard": "SAFE"}}
```

`type`은 64자 이하 자유 문자열입니다. 참여자 식별 정보는 넣지 않습니다.
