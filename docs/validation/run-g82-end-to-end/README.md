# G82 실제 흐름 점검: LLM 형태 이름, 참여자 화면 끝까지, 합성 대사 (2026-11-28)

G82는 [맞는 게 없어요] 뒤 규칙 그림 프롬프트에 중심 형태 명사가 없을 때, 면담 LLM이 확정 텍스트에서 형태 낱말 하나를 인용하고 영어 이름을 내는 경로다(`chatbot/ifs_chatbot/llm_shape.py`). 이 점검은 그 경로를 참여자 화면에서 처음부터 끝까지 돌렸다. 합성 문장은 9개다(G81에서 실패한 사전 밖 형태 4, 새 사전 밖 형태 2, 막혀야 하는 문장 2, [그 말이 아니에요] 1). 제품 코드·사전·프롬프트·설정은 고치지 않았다.

## 무엇을 어떻게 돌렸나

- 서버: `chatbot/config/experiment-g82.toml`을 저장소 밖 임시 폴더에 복사하고 `[session] log_dir`만 그 폴더로 바꿨다(나머지는 같다). `chatbot/.venv` 파이썬으로 `--port 8011`에 띄웠고, `--researcher-contact`는 합성 점검용 문구다. 8000번 서버와 Unity 에디터는 건드리지 않았다. 점검이 끝난 뒤 8011 서버만 내렸다.
- `run_g82_e2e.py`(G81 `run_g81.py`와 같은 방식)
  1. HTTP로 면담을 진행한다. 세션 `SYN-G82-<ID>-1`을 만들고 첫 답에 합성 문장을 넣는다. 나머지 질문은 [넘어가기]로 넘기고, 확인 화면에서 [고칠게요]로 확정 텍스트를 그 문장으로 맞춘다. 면담 LLM과 가드는 실제 모델이다.
  2. 헤드리스 Chrome(1280px)으로 참여자 화면을 열고 단추를 누른다. 순서는 [다음으로] → 후보 → [맞는 게 없어요] → (LLM·그림 대기) → 그림 고르기(근거 인용 줄이 있으면 `b_images_basis`로 찍음) → **맨 앞(가장 작은 seed) 그림**을 기계적으로 고름 → 만든 물체 → 그 물체를 고름 → 조절 → [다 고쳤어요]이다. `reject` 표시 문장(E9)은 그림 고르기 화면에서 [그 말이 아니에요]를 누르고 그 뒤 화면을 찍는다. 막히면 그때 화면을 찍는다.
  3. 찍을 때마다 화면 글에 세션 ID·로컬 경로가 있는지 검사해 `privacy`에 적는다. 9문장 35장 모두 걸린 것이 없었다.
  4. 세션마다 spec, `selection.json`, 세션 로그에서 매퍼 형태 슬롯, `generation.shapeLlm`, `afterNone`(`shapeLlmUsed`·`shapeLlmItems`·`basisRejected`), 그림 프롬프트, 그림 관문, 메시 관문, 단계별 시간, `runnerReady`를 모아 `results.json`에 넣는다. 간추린 값은 `collected.summary`에 있다. 로컬 경로는 `<logs>/`·`<gen3d-out>/`·`<repo>/`로 바꿨다.
- `make_summary.py`: `results.json`과 그림·메시 축소판(저장소 밖)으로 `summary_1.png`(E1–E5)·`summary_2.png`(E6–E9)를 만든다(폭 1600px).
- 다시 돌리기(서버를 위 사본 설정으로 띄운 뒤):
  `python run_g82_e2e.py --logs <log_dir> --raw <임시 폴더> [--cases cases.json] [--out <폴더>] [--sid-prefix SYN-G82] [--tag 2]`
  이어서 `python make_summary.py --raw <임시 폴더> [--out <폴더>] [--judge judge.json]`. `--cases`는 `[{"id", "kind", "text", "reject"}]` 꼴이고, 없으면 아래 9문장을 쓴다. 필요한 패키지는 websockets와 Pillow다.

## 모델·설정

| 역할 | 모델 · 리비전/digest |
| --- | --- |
| 면담·G77·G82 | `gemma4:e4b` `sha256:dc35e8d9c6061baa6f0fa870975ab6932e2542b579b13ea0f199fa4bb7300c9c` (Ollama 0.40.17). G82: 프롬프트 `llm_shape.v0.3.0`(draft, sha256 `0f3c2440…7c1e66`), 검증기 `ifs-llm-shape-validator/0.5.0`, 온도 0, seed 0, 한도 20초 |
| 가드 | `kanana-safeguard-8b-GGUF:Q4_K_M` `34ca9739d8a4bcf9127501b114b775af807b48f7ce64befeec115d308c927c69` |
| 그림 | `stabilityai/stable-diffusion-xl-base-1.0` @ `462165984030d82259a11f4367a4eed129e94a7b` |
| 형태 | `VAST-AI/TripoSG` @ `2c1c516d22d58db486a058d98d31bb6177344e06`, 배경 제거 rembg u2net |
| 관문 | `openai/clip-vit-large-patch14` @ `32bd64288804d66eefd0ccbe215aa642df71cc41` (문턱 0.5) |

매퍼 builder는 `scene-spec-builder-v2/2.9.0`(spec 2.4.0), 그림 프롬프트는 `gen3d-shape-prompt/0.4.0+imagepick+mapper-v2+llmshape-0.1.0`, 선택 문구는 `selection_protocol.v0.12`다. 미리보기는 WebGL이다. GPU는 RTX 5080 16 GB를 썼다. 시작할 때 VRAM 8.1 GB가 쓰이고 있었고, Ollama에는 `gemma4:e4b` 하나가 올라와 있었다(8000번 서버와 같은 Ollama). 실행 도중 21:02:31에 8000번 서버가 다른 쪽에서 다시 시작됐다(이 점검이 한 일이 아니다). 그래도 GPU 때문에 실패한 경우는 없었다. 실행 시간은 20:55–21:04(약 9분 30초)였다.

## 결과

"누름→다음"은 [맞는 게 없어요]를 누른 때부터 다음 화면까지다. LLM 호출, 그림 3장, 관문, 모델 내리기·적재를 포함한다. "고름→다음"은 그림을 고른 때부터 만든 물체가 든 후보 화면(또는 막힌 뒤 조절 화면)까지다. "끝까지"는 [다 고쳤어요]를 눌러 사전 측정 화면에 닿았는지를 뜻한다. 9문장 모두 끝까지 갔고 `runnerReady: true`였다.

| ID | 입력 | 매퍼 형태 | LLM 부름 · 출력 | 채택 인용 → 영어 | 그림(관문) | 메시 | 끝까지 · 시간 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E1 | 조약돌이 하나 있어요. | 없음('조약돌' `_unmapped`) | 예 · 0.62초 | '조약돌이' → pebble | 3장 모두 통과 | 만듦, 고름(`generated_chosen`) | 예 · 누름→다음 80.6초(첫 SDXL 적재), 고름→다음 61.0초 |
| E2 | 판때기예요. 겨자색이고 반지르르해요. | 없음 | 예 · 0.42초 | '판때기예요' → board | 2장 통과, seed 2 막힘(0.961) | 만듦, 고름. G77 색 yellow·질감 smooth | 예 · 41.4초, 42.9초 |
| E3 | 돌덩이 같은 게 있어요. | 없음('돌덩이' `_unmapped`) | 예 · 0.27초 · **null** | — | 시작 안 함(`no_shape_stated`) | — | 예 · 3.2초 |
| E4 | 돌덩이예요. | 없음('돌덩이' `_unmapped`) | 예 · 0.30초 · **null** | — | 시작 안 함(`no_shape_stated`) | — | 예 · 3.1초 |
| E5 | 꼭 주전자 같아요. 회색이에요. | 없음('주전자' `_unmapped`) | 예 · 0.39초 | '주전자' → kettle | 3장 모두 통과(최대 0.022) | **메시 관문에서 막힘**(`person_like` 0.793) | 예 · 39.9초, 41.4초 뒤 「물체를 더 만들지 못했어요」 |
| E6 | 머릿속에 톱니바퀴가 있어요. | 없음('톱니바퀴' `_unmapped`) | 예 · 0.42초 | '톱니바퀴가' → gear | 2장 통과, seed 2 막힘(0.740) | 만듦, 고름 | 예 · 39.9초, 45.9초 |
| E7 | 쑥색이고 차가워요. | 없음 | 예 · 0.25초 · null | — | 시작 안 함(`no_shape_stated`) | — | 예 · 3.2초. 의도대로(원칙 2) |
| E8 | 돌덩이처럼 단단해요. | 없음 | 예 · 0.30초 · null | — | 시작 안 함(`no_shape_stated`) | — | 예 · 3.1초. 의도대로(속성 비유) |
| E9 | 조약돌이 하나 있어요. + [그 말이 아니에요] | 없음 | 예 · 0.44초 | '조약돌이' → pebble | 3장 모두 통과(E1과 같은 그림) | 만들지 않음 | 예 · 38.4초, 누른 뒤 2.1초에 조절 화면 |

- 기록: 채택된 다섯 문장에서 `shapeLlm.route = llm`, `afterNone.shapeLlmUsed = true`, `shapeLlmItems` = 채택 인용·영어였다. 그림 화면에 나온 뒤 `exposed = true`, 그림을 고르면 `imageChosen = true`, 만든 물체를 고르면 `candidateChosen = true`가 됐다. E9는 `rejected = true`, `afterNone.basisRejected = true`, `imagePick.outcome = basis_rejected`, `afterNone.status = declined`였고 메시는 만들지 않았다. LLM이 null을 낸 네 문장은 `route = none`, `routeReason = null`, `rawText = {"item": null}`이다. 다섯 문장 모두 검증기 기각(`rejectReasons`)은 없었다.
- 근거 인용 줄: 채택된 다섯 문장 모두 그림 고르기 화면 맨 위에 「'<인용>'라고 하신 말을 바탕으로 모양을 만들어 볼게요.」와 [그 말이 아니에요]가 나왔다(`shots/E*_b_images_basis.png`). 영어 이름은 화면에 나오지 않았다.
- 만든 물체를 고른 세 세션(E1·E2·E6)의 `sources["form.type"]`은 `generated_chosen`이다. 나머지는 `default`다.
- 눈으로 본 판단(참고용, 점검자 한 사람의 판단이며 측정이 아님): E6 톱니바퀴는 그림 두 장과 메시 모두 톱니바퀴로 알아볼 만했다. E1 pebble은 seed 0이 고리 모양 덩어리, seed 1이 조약돌, seed 2가 받침 위의 돌이었다. 맨 앞 그림(고리)을 골라 메시도 고리 모양이 됐다. E2 board는 seed 0이 동심원이 새겨진 둥근 판, seed 1이 달걀 모양이었다. 판때기(넓적한 판)보다 원반에 가깝고, 메시도 겨자색 원반이다. E5 kettle은 그림 세 장 모두 주전자로 알아볼 만했다(seed 0은 몸통에 구멍).

## 찾은 문제 (재현 입력)

1. **'돌덩이'는 G82에서도 형태를 만들지 못한다.** 재현: 「돌덩이예요.」(E4), 「돌덩이 같은 게 있어요.」(E3). 규칙은 `no_shape_stated`로 LLM을 불렀다. 그런데 모델이 두 꼴 모두 `{"item": null}`을 냈다(온도 0이라 같은 문장은 같은 결과). G81에서 실패한 네 문장 가운데 G82로 풀린 것은 조약돌·판때기 둘이다. 돌덩이 둘은 그대로다. 근거: `results.json` `cases.E3/E4.collected.selection.generation.shapeLlm.rawText`.
2. **주전자 메시가 메시 관문에서 사람 모양으로 막힌다.** 재현: 「꼭 주전자 같아요. 회색이에요.」(E5). 그림 관문은 세 장 모두 통과했다(사람·동물 점수 0.017–0.022). 고른 그림(seed 0)으로 만든 메시는 관문에서 `personLikeScore` 0.793으로 막혔고, 그 가운데 "a head with eyes and a mouth"가 0.682였다. 참여자는 그림을 고른 뒤 41초를 기다렸다가 「물체를 더 만들지 못했어요. 이어서 진행할게요.」와 함께 조절 화면으로 갔다. 다음 회차(새 seed)는 제안되지 않는다. 근거: `shots/E5_c_no_mesh_adjusting.png`, 생성기 사이드카 `<gen3d-out>/none-SYN-G82-E5-1-…-r0-mesh/g62-sdxl-triposg/assets/after-none.form-asset.json`의 `gate`.
3. **막힌 메시의 관문 점수가 `selection.json`에 남지 않는다(기록).** E5의 `afterNone`은 `status blocked`, `blockReason person_like`뿐이고 `asset`은 null이다. 점수 0.793과 라벨 점수는 저장소 밖 생성기 사이드카에만 있다. 같은 E5에서 `shapeLlm.candidateChosen`은 `false`다. 만든 물체가 화면에 나온 적이 없으므로 `null`(그림 단계에서 끝난 E9와 같은 뜻)이 맞는지 확인이 필요하다.
4. **[그 말이 아니에요]를 누른 뒤 안내 문구가 없다.** 재현: E9. 누르면 2.1초 뒤 조절 화면으로 가지만 「물체를 더 만들지 못했어요…」(`none_gen_unavailable`)가 나오지 않는다(`shots/E9_b2_after_reject_adjusting.png`). `shared/protocol/selection_protocol.v0.12.json`의 `llm_shape_basis_wrong_button` 주석은 "기존 none 경로(0번 후보로 조절, none_gen_unavailable 안내)"라고 적었다. 그러나 `chatbot/ifs_chatbot/web/stage.js`(조절 화면 `genNote`)는 `afterNone.status`가 blocked·failed·timeout일 때만 그 줄을 보인다. `reject_shape_basis`는 status를 `declined`로 둔다. 코드와 문구 주석 가운데 어느 쪽이 맞는지 정해야 한다.
5. **인용에 조사·서술격 조사가 붙어 화면 문장이 어색하다.** E1·E9 '조약돌이', E2 '판때기예요', E6 '톱니바퀴가'. 화면에는 「'판때기예요'라고 하신 말을 바탕으로 모양을 만들어 볼게요.」처럼 나온다. 원문 글자 그대로이므로 원칙은 어기지 않는다. 또 모델이 낸 `charSpan`은 다섯 문장 가운데 셋(판때기예요 [0,4], 주전자 [2,6], 톱니바퀴가 [5,11])이 인용 글자 수와 한 칸씩 어긋났다. `repair_span`이 고쳐서 채택됐다(`rawItem`과 `adopted` 비교).
6. **(작음, 화면)** 근거 인용 줄 옆 [그 말이 아니에요] 단추가 줄 폭의 약 60%를 차지한다. 그래서 그림마다 붙은 [이걸로 할게요]보다 커 보인다(`shots/E1_b_images_basis.png`). 단추 무게를 같게 하려는 G73의 방침과 맞는지 확인이 필요하다.
7. **(G81에서 이미 알려짐)** 그림의 받침: E1 seed 2(받침 위 돌)가 부정 틀에 stand·pedestal이 있는데도 화면에 나왔다.

## 한계

- 문장마다 한 번씩만 돌렸다. 그림은 기계적으로 seed 0을 골랐다. [이 중에는 없어요]로 가는 2회차와 다른 그림을 고른 경우는 보지 않았다.
- E9는 E1과 같은 문장이라 그림 단계가 캐시를 탔을 수 있다. 관문 점수가 E1과 같았다. 첫 그림 단계(E1 80.6초)에는 SDXL 첫 적재가 들어 있다. 나머지 그림 단계는 38–41초, 형태 단계는 41–61초였다.
- 면담 질문은 [넘어가기]로 넘겼다. 그래서 면담 LLM이 형태를 되묻는 경로는 보지 않았다. 확정 텍스트는 한 줄이라 G82의 단계 표지(찾기·머물기·구체화) 규칙은 이 점검에서 걸리지 않는다.
- E8(속성 비유)은 LLM이 null을 내서 막혔다. 검증기의 속성 비유 규칙은 이 실행에서 일하지 않았다(3차 오프라인 평가와 같은 상황).
- 헤드셋 러너로 `selection.json`을 읽혀 보지 않았다.
- 서버는 `chatbot/.venv` 파이썬으로 띄워야 한다. 처음에 kiwipiepy가 없는 시스템 파이썬으로 띄웠다가 "kiwipiepy가 없어 정규식 대체 분석" 경고를 보고 세션을 만들기 전에 내렸다. 이 실행의 결과는 모두 venv 서버의 것이다.
- 눈으로 본 판단은 점검자 한 사람의 참고 의견이다.

## 파일

- `run_g82_e2e.py`, `make_summary.py`: 돌린 스크립트
- `results.json`: 문장별 원시 결과. `collected.summary`(shapeLlm·afterNone·관문·runnerReady 간추림), `collected.selection.generation`(원본), `collected.spec`(매퍼 형태 슬롯), `steps`(화면 상태), `timings`, `privacy`(찍은 화면의 세션 ID·경로 검사, 모두 빈 목록)
- `summary_1.png`(E1–E5), `summary_2.png`(E6–E9): 문장·매퍼 형태·LLM 인용→영어·그림 3장(고른 그림 초록, 관문에 막힌 그림 빨강)·메시·결과를 모은 요약 시트
- `shots/<ID>_<단계>.png`: `a_candidates` 후보, `wait_llm_image`·`wait_mesh` 대기, `b_images_basis` 근거 인용 줄이 있는 그림 고르기, `c_mesh` 만든 물체가 맨 앞에 든 후보, `d_adjust` 조절, `d_adjust_blocked` 막혔을 때 참여자가 보는 화면, `E5_c_no_mesh_adjusting` 메시 관문에 막힌 뒤 화면, `E9_b2_after_reject_adjusting` [그 말이 아니에요] 뒤 화면
- 원본 세션 기록, 그림·메시 축소판, 생성 산출물(`gen3d-out/none-SYN-G82-*`)은 git 밖에 있다.
