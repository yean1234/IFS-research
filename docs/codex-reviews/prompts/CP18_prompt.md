너는 이 연구 저장소의 외부 감시자(코드 리뷰어)다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라. 경로는 저장소 기준 상대 경로로만 적어라.

## 맥락
- 원칙 `AGENTS.md`(원칙 2·3·5·6·7), 뼈대 `docs/design-backbone.md` 2절, 결정 `docs/decisions.md`의 **G79 절**(구현 명세), 설계 `docs/chatbot-design.md` 7.4·7.12, 앞선 설계 문서 `docs/codex-reviews/D14.md`, `D14_claude.md`, `D14_rebuttal.md`.
- 검토 범위: **커밋 전 작업 트리**의 G79 변경. `git diff -- chatbot/ shared/schemas/selection.v0.5.json`과 새 파일 `shared/lexicon/candidate_values.v4.json`, `shared/protocol/selection_protocol.v0.11.json`, `chatbot/ifs_chatbot/eval/color_bins.py`, `chatbot/tests/test_g79_color_ring.py`. 핵심은 `chatbot/ifs_chatbot/selection.py`의 `ring_hue`, `_ring_setup`, `_ring_pos`, `_validate_ring`, `_ring_record_new`/`_ring_enter`/`_ring_final`/`_ring_view`와 `chatbot/ifs_chatbot/web/stage.js`의 `colorRing`, `style.css`.
- `unity/`, `docs/run-experiment.md`, `docs/headset-checklist.md`는 다른 작업이다. 보지 마라.

## 이미 알고 있는 것 (되풀이하지 말 것)
- 선택 파일 형식은 0.5 그대로 두고 선택 속성만 더했다(G79-e). 명도는 조절 항목으로 두지 않는다(G79-b).
- 채도 단계 [0.25, 0.4, 0.6, 0.85]는 잠정값이다. 헤드셋에서 5° 차이·단계 차이가 보이는지, 웹 색과 Unity 렌더 색의 차이는 사람이 본다.
- 매퍼의 색상은 소수 셋째 자리라, 칸 값과 0.0005 안이면 그 칸을 말한 값으로 본다.
- 같은 색을 다시 누르거나 Home을 눌러도 조작 횟수가 올라간다. 낭독기 이름에 "채도"라는 말이 들어간다. `exposed`는 서버가 조절 화면을 내보냈는지 기준이다.

## 관점
1. **입력 검증**: `hueStep`·채도 단계에 대한 경계와 형식(72, -1, 1.0, "3", true, null, 큰 수, NaN, 배열, 키가 여럿인 입력, 견본 id와 hueStep을 함께 보낸 입력). 검증을 지나 스펙·선택 파일에 범위 밖 HSL이 들어가는 경로. 말한 값 허용이 다른 세션·다른 후보로 새는 경로.
2. **원칙 2**: 말하지도 고르지도 않은 상태가 어느 경로에서든 `picked`·`edited`로 적히거나, 고른 것이 `unspecified`·`default`로 적히는 경우(화면을 열기만 함, 채도만 누름, 무채색 견본에서 고리로, 고리에서 처음 값으로 돌아옴, 후보를 바꾼 뒤, 새로고침·재접속 뒤). 말한 색이 고리 조작 없이 바뀌는 경로. `sources`·`colorChanged`와 `colorRing.final.origin`이 서로 어긋나는 경우.
3. **G77·위기 판정과의 맞물림**: llm_quoted 색 제안, 위기·확인 판정 세션의 처음 값, 그림 고르기(G75) 흐름에서의 회귀.
4. **v3 설정 불변**: `experiment.toml` 밖 설정의 화면·기록 바이트가 그대로인가. v4를 켰는데 프로토콜이 0.10이거나 그 반대인 설정 조합이 시작 때 걸러지는가.
5. **화면**: 외부 URL·CDN, XSS(서버가 준 값을 DOM에 넣는 방식), 끄는 동안 `adjust`가 여러 번 나가는 경로, 터치·포인터 캡처 누락, 키보드만으로 모든 조작이 되는가, aria·보이는 글에 색 이름·평가하는 말이 있는가.
6. **분석 함수 `color_bin`**: 경계(s=0.10, h가 칸 경계, h=1.0)와 결정성. 화면·기록으로 새는 경로.
7. **문구(원칙 7)**: 새 키의 status·출처·판, 옛 판 파일 보존.
8. **시험의 빈틈**과 문서 불일치.

## 출력 형식
지적마다: 심각도(높음/중간/낮음), `파일:줄`, 재현 입력 또는 경로, 왜 문제인지, 고칠 방향 한 줄. 심각도 순. 끝에 "문제없다고 확인한 것". 추측은 추측이라고 밝혀라.
