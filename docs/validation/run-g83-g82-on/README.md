# G83 실제 흐름 재확인: G82를 켠 experiment.toml, 합성 대사 (2026-11-28)

연구 책임자가 G82(LLM이 생성 프롬프트의 형태 낱말을 제안)를 실험 설정에서 켜기로 정했다(G83). 켜기 전에 G82 첫 점검(`docs/validation/run-g82-end-to-end/` '찾은 문제' 3–6)에서 찾은 화면·기록 문제 네 가지를 고쳤다. 이 점검은 그 수정이 참여자 화면과 `selection.json`에 실제로 나타나는지 본다.

| | 문제(G82 점검) | 고친 방식 |
| --- | --- | --- |
| a | [그 말이 아니에요] 뒤 안내 없이 조절 화면으로 감 | 선택 보기 `afterNone`에 `basisRejected`를 넣고, `stage.js` 조절 화면의 안내 줄 조건에 `basisRejected === true`를 더함. 문구는 기존 `none_gen_unavailable` 그대로 씀 |
| b | 인용에 조사가 붙어 화면 문장이 어색함('판때기예요'라고 하신 말을…) | 화면 낱말 = LLM 인용 구간 안의 첫 명사 덩어리(확정 텍스트 글자 그대로의 부분 구간, Kiwi 품사, `llm_shape.basis_display`). 문구 0.13.0에서 `{rago}` 자리에 받침에 맞춘 '이라고'/'라고'. 기록 `generation.shapeLlm.basisShown`에 LLM 인용·화면 구간 둘 다 남김 |
| c | [그 말이 아니에요] 단추가 그림 단추보다 큼 | 근거 줄을 `none-fit-row`에서 떼어 자체 배치(`.llm-shape-basis`). 단추 폭 = 그림 칸 하나의 [이걸로 할게요] 폭(그림 3·2·1장 각각) |
| d | 막힌 메시의 관문 점수가 기록에 없음. 물체가 화면에 나온 적 없어도 `candidateChosen` false | 메시 단계가 막히면 사이드카 `gate`를 `afterNone.gate`로. `shapeLlm.candidateExposed`를 더하고, 만든 물체가 후보 화면에 나온 적이 있을 때만 `candidateChosen` false(아니면 null) |

## 무엇을 어떻게 돌렸나

- 서버: `chatbot/config/experiment.toml`(G83: `[gen3d] on_none_llm_shape = true`, `[selection] protocol = selection_protocol.v0.13.json`)을 저장소 밖 임시 폴더에 복사하고 `[session] log_dir`만 그 폴더로 바꿨다. `chatbot/.venv` 파이썬으로 `--port 8011`에 띄웠다(Kiwi 0.24.1, 가드 모델 있음). 서버 시작 경고에 "on_none_llm_shape가 켜져 G77의 형태 낱말 칸(shape_noun)은 내밀지 않습니다"가 나왔다. 8000번 서버와 Unity는 건드리지 않았다. 점검이 끝난 뒤 8011 서버만 내렸다.
- `run_g83_e2e.py`: G82 점검 스크립트(`run-g82-end-to-end/run_g82_e2e.py`)를 그대로 불러 쓰고 두 가지를 더했다. 화면 정보에 [그 말이 아니에요]와 첫 그림 단추의 크기(px), 조절 화면 안내 줄 글을 넣었다. results.json 간추림에 `basisShown`·`candidateExposed`·`afterNone.gate`·`shapeLlmBasisShown`을 넣었다. 드라이버는 websockets·Pillow가 있는 시스템 파이썬으로 돌렸다(드라이버는 챗봇 코드를 불러오지 않는다).
- 문장: `cases.json`. 지시받은 합성 4문장(R1 조약돌, R2 판때기, R3 톱니바퀴, R4 조약돌 + [그 말이 아니에요])에 R5 주전자를 덧붙였다. R5는 d의 메시 관문 차단 기록을 실제 흐름에서 보려고 넣었다(G82 점검 E5와 같은 문장).
- R2는 두 번 돌렸다. 첫 실행(`SYN-G83-R2-1`)에서 관문으로 그림이 2장만 보여 그림 단추가 381px, [그 말이 아니에요]가 240px였다. 그래서 그림 2장·1장일 때의 폭 규칙을 더하고 R2만 다시 돌렸다(`SYN-G83-R2-2`, `--resume`). results.json의 R2와 `shots/R2_*`, `run` 시각은 두 번째 실행 것이다.
- 요약 시트: `make_summary.py`(G82 것을 그대로 돌리고 부제의 설정 이름만 바꿈) → `summary_1.png`.
- 다시 돌리기: 위처럼 서버를 띄운 뒤 `python run_g83_e2e.py --base http://127.0.0.1:8011 --logs <log_dir> --raw <임시 폴더> --cases cases.json --sid-prefix SYN-G83`, 이어서 `python make_summary.py --raw <임시 폴더> --title "G83 실제 흐름 재확인(G82 켬)"`.

모델은 G82 점검과 같다: 면담·G77·G82 `gemma4:e4b` `sha256:dc35e8d9…c9c`(Ollama 0.40.17), G82 프롬프트 `llm_shape.v0.3.0`, 검증기 `ifs-llm-shape-validator/0.5.0`, 그림 SDXL base 1.0, 형태 TripoSG, 관문 CLIP ViT-L/14(문턱 0.5). 선택 문구 `selection_protocol.v0.13.json`(0.13.0), 화면 낱말 규칙 `ifs-llm-shape-basis-display/0.1.0`. 실행 시각은 21:57–22:05.

## 결과

5문장 모두 [다 고쳤어요]까지 가서 사전 측정 화면에 닿았다. 찍은 화면 27장에서 세션 ID·로컬 경로가 보인 곳은 없었다(`privacy`). 콘솔 오류는 없었다(WebGL 빌드의 Unity 경고 한 줄만).

| ID | 입력 | LLM 인용 → 화면 낱말(구간) | 화면 문장 | 단추 폭(아니에요 / 그림 단추) | 결과 · 기록 |
| --- | --- | --- | --- | --- | --- |
| R1 | 조약돌이 하나 있어요. | '조약돌이' [0,4] → '조약돌' [0,3] | 「'조약돌'이라고 하신 말을 바탕으로 모양을 만들어 볼게요.」 | 240 / 240 (그림 3장) | 그림 고름 → 메시 → 고름. `candidateExposed` true, `candidateChosen` true |
| R2 | 판때기예요. 겨자색이고 반지르르해요. | '판때기예요' [0,5] → '판때기' [0,3] | 「'판때기'라고 하신 말을 …」 | 381 / 381 (그림 2장, seed 2 관문 0.961) | 그림 고름 → 메시 → 고름. `candidateChosen` true |
| R3 | 머릿속에 톱니바퀴가 있어요. | '톱니바퀴가' [5,10] → '톱니바퀴' [5,9] | 「'톱니바퀴'라고 하신 말을 …」 | 240 / 381 (그림 2장, seed 2 관문 0.740 — 폭 규칙을 더하기 전 실행) | 그림 고름 → 메시 → 고름. `candidateChosen` true |
| R4 | 조약돌이 하나 있어요. + [그 말이 아니에요] | '조약돌이' → '조약돌' | 「'조약돌'이라고 하신 말을 …」 | 240 / 240 | 누른 뒤 2.1초에 조절 화면. 맨 위에 「물체를 더 만들지 못했어요. 이어서 진행할게요.」(a). `afterNone.status` declined, `basisRejected` true, `shapeLlm.rejected` true, `candidateExposed` false, **`candidateChosen` null**(d) |
| R5 | 꼭 주전자 같아요. 회색이에요. | '주전자' [2,5] → '주전자'(줄일 것 없음) | 「'주전자'라고 하신 말을 …」 | 240 / 240 | 그림 고름 → 메시가 관문에서 막힘(`person_like`). 조절 화면 맨 위에 같은 안내. **`afterNone.gate`** = personLikeScore 0.7934, passed false, threshold 0.5, labelScores 포함(d). `imageChosen` true, `candidateExposed` false, **`candidateChosen` null** |

- a: R4·R5 조절 화면에 안내 줄이 보였다(`shots/R4_b2_after_reject_adjusting.png`, `shots/R5_c_no_mesh_adjusting.png`). 연구자 보기 줄은 R4에서 `생성 declined: basis_rejected`다.
- b: 줄인 세 경우 모두 화면 낱말이 확정 텍스트의 부분 구간이었고(`shownSpan`), 원문에 없는 글자는 없었다. 조사는 받침대로 나왔다(조약돌 → 이라고, 판때기·톱니바퀴·주전자 → 라고). `fallback`은 모두 null이었다. 영어 이름은 화면에 없었다.
- c: 그림 3장(R1·R4·R5)과 2장(R2 두 번째 실행)에서 [그 말이 아니에요]와 [이걸로 할게요]의 폭·높이가 같았다(`shots/R1_b_images_basis.png`, `shots/R2_b_images_basis.png`). R3은 2장 규칙을 더하기 전에 돌려 240 / 381이다(단추가 더 작음). 다시 돌리지 않았다.
- d: 위 표. 메시가 만들어지고 고른 R1–R3은 예전처럼 `candidateChosen` true다.
- 시간: [맞는 게 없어요] → 그림 화면 37–46초, 그림 고름 → 다음 화면 10–11초다. 형태 단계의 생성기 시간이 6초 안팎이었다. G82 점검의 같은 그림·seed 산출물을 생성기가 다시 썼을 수 있다(확인하지 않음). 실제 참여자 세션에서는 형태 단계가 40–60초 걸릴 수 있다(G82 점검 수치).

## 한계

- 문장마다 한 번씩(R2는 두 번)만 돌렸다. 그림은 맨 앞 그림을 기계적으로 골랐다. [이 중에는 없어요]로 가는 2회차는 보지 않았다(단위 시험 `test_second_round_reuses_without_recall`만).
- 화면 낱말 규칙이 인용 전체로 돌아가는 경우(명사 없음·축약)는 실제 흐름에서 나오지 않았다. 단위 시험(`chatbot/tests/test_g83_g82_on.py`)으로만 확인했다.
- 그림 1장·좁은 화면(한 줄 한 칸)의 단추 폭은 화면으로 보지 않았다(CSS 규칙만).
- 헤드셋 러너로 `selection.json`을 읽혀 보지 않았다. 새 칸은 `generation` 아래에만 더했고, 러너는 그 키를 읽지 않는다.

## 파일

- `run_g83_e2e.py`, `make_summary.py`, `cases.json`: 돌린 스크립트와 문장
- `results.json`: 문장별 원시 결과(`collected.summary`에 shapeLlm·afterNone 간추림, `steps`에 화면 상태·단추 크기·안내 줄 글). 로컬 경로는 `<logs>/`·`<gen3d-out>/`·`<repo>/`로 바꿨다
- `summary_1.png`: 문장·매퍼 형태·LLM 인용→영어·화면 문장·그림 3장(고른 그림 초록, 관문에 막힌 그림 빨강)·메시·결과
- `shots/<ID>_<단계>.png`: `a_candidates`, `wait_llm_image`·`wait_mesh`, `b_images_basis`(근거 줄), `c_mesh`, `d_adjust`, `R4_b2_after_reject_adjusting`, `R5_c_no_mesh_adjusting`
- 원본 세션 기록·그림·메시 축소판·생성 산출물은 git 밖에 있다.
