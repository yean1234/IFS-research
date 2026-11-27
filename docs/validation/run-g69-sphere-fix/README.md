# run-g69-sphere-fix — 구형이라고 말했는데 천이 그려지던 문제 (매퍼 v2 builder 2.6.0, 2026-11-27)

입력은 연구 책임자가 `--config experiment`로 해 본 시험 세션의 답 9줄이다(연구자 시험 입력, **합성 표기** — 참여자 응답이 아님).
확정 텍스트와 같은 꼴(답마다 한 줄)로 매퍼 v2에 넣었다. 회귀 시험: `chatbot/tests/test_g69_shape_priority.py`.

| 파일 | 내용 |
| --- | --- |
| `specs/SYN-G69-before.json` | builder 2.4.0(고치기 전): `form.base = sheet`(천, drape cloth), 모양어 round 셋은 `not_applied_base` |
| `specs/SYN-G69-after.json` | builder 2.6.0: `form.base = null`(천은 `_alternatives` lower_priority `+actionSimile(펄럭이듯이)`), 모양어 round(구형·동그랗·구체), 크기 0.5(보통), 거칠기 0.7(무광), 빠르기 없음 |
| `SYN-G69-before.png` · `SYN-G69-after.png` | 위 spec을 Unity Windows 미리보기 플레이어(`webgl-build/preview-win/IFSPreview.exe`, 2026-11-23 빌드, 덮어쓰기 없음, 640×480)로 그린 것. 고치기 전 직사각형 천, 고친 뒤 구(모양 모형 Sphere) |

배치 캡처(`BatchCapture.Run`)는 같은 프로젝트를 연 Unity 편집기가 있어 돌리지 못했다. 미리보기 플레이어는 저장소 밖 빌드라 최신 Unity 코드와 다를 수 있다.
