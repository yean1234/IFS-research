# G73 [맞는 게 없어요] 뒤 형태 생성: 실제 생성기로 확인 (2026-11-27)

experiment 설정 서버를 띄우고(면담 LLM `gemma4:e4b`·가드 모델 실제, Ollama), 합성 세션을 HTTP로 면담 → 확정까지 진행한 뒤 헤드리스 Chrome(DevTools 프로토콜)으로 참여자 화면에서 [다음으로] → [맞는 게 없어요]를 눌렀습니다. 생성기는 저장소 밖 `gen3d-venv`의 `tools/gen3d/generate.py --pipeline sdxl-triposg`(SDXL base 1.0 → rembg → TripoSG `2c1c516d`, CLIP 관문), RTX 5080 16 GB. 대사는 모두 합성이거나 연구 책임자 시험 대사입니다.

| 세션 | 확정 텍스트(요지) | 규칙 프롬프트 | 결과 | none → 화면 바뀜 |
| --- | --- | --- | --- | --- |
| R1 | 연구 책임자 시험 대사(`scenarios/g70_researcher_finish.json`) | a single round cloth | 만들지 않음 `no_shape_preview` — 미리보기가 글 요약으로 내려간 세션(아래 ①) | 즉시 |
| R2 | R1과 같음(① 피하려고 `mist_kinds = ""` 임시 설정) | a single round cloth (낱말 '동그란' [95,98], '천' [50,51]) | 생성됨, CLIP 관문이 `person_like`로 막음 → 기존 none 경로 | 100.3초(모델 내림 0.6 + 생성기 99.0, 캐시 없음) |
| R3 | 「…엉킨 실타래 같아요…」 | a single tangled ball of yarn ('엉킨' [15,17], '실타래' [18,21]) | 성공, 맨 앞에 더함 → 골라 조절로. GLB가 `selection/<세션>/form-asset-*.glb`로 복사, `sources.form.type = generated_chosen`, `form.asset.origin = generated_after_none` | 9.4초(같은 프롬프트·seed 0 캐시 적중, 모델 호출 없음) |
| R4 | R3과 같음 | 같음 | seed 0 성공(캐시) → 다시 [맞는 게 없어요] → **seed 1로 다시 만들기** 성공 → 그것을 고름 | 12.4초 / 다시 만들기 63.5초(생성기 62.5, 모델 적재 포함) |

- 모든 회차에서 생성 전 `/api/ps`의 두 모델(면담·가드)이 내려갔고(`loadedAfter: []`), 끝난 뒤 다시 올라왔습니다.
- 화면: `*_2_waiting.png` 대기 화면(R1은 막혀서 대기 화면 없이 조절로 감), `*_3_selecting.png` 만든 물체가 맨 앞 점선 칸, `R2_3_adjusting.png` "물체를 더 만들지 못했어요. 이어서 진행할게요.", `R4_3c_regen_selecting.png` 다시 만든 것(맨 앞)과 처음 만든 것.
- 헤드셋 러너 자동 시행(`RunAutoTrialBatch`)은 Unity 프로젝트가 다른 Unity 인스턴스에 열려 있어 돌리지 못했습니다. R4의 `selection.json`(0.3, `runnerReady: true`)은 G62 러너 계약과 같은 꼴입니다(`form.asset.glb` 상대 파일 이름 + sha256, `sources.form.type = generated_chosen`).

발견(이 작업 범위 밖):
1. 지금 `experiment.toml`의 `[mapping] mist_kinds`(G74, 작업 중)를 켠 채로는 WebGL·Windows 미리보기 빌드가 spec의 `form.mistKind`를 몰라 spec을 읽지 못하고, 그 세션은 글 요약으로 내려갑니다(R1). 글 요약 세션에서는 생성 후보를 보일 수 없어 G73이 만들지 않습니다. 미리보기 빌드를 다시 만들어야 합니다.
2. R2 spec(모양어 '구형·동그란' → 구 모형)에서 WebGL 준비 그리기(형태 값마다 미리 그림)가 `form.type=mist` + 구 모형 덮어쓰기를 거부해 image로 내려가고, 조절 중 image 플레이어도 같은 이유로 실패해 글 요약으로 내려갔습니다. G73 이전부터 있는 미리보기 문제로 보입니다.
3. CLIP 사람·동물 관문이 '둥근 천'을 `person_like`로 막았습니다(G62 평가의 관문 오탐과 같은 문제).

원본 기록(`chatbot/logs/`, 생성기 입력·로그 `gen3d-out/none-SYN-G73-R*`)은 git 밖입니다.
