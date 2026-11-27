# CP13 구현 검토: G73 CP13a (다시 적은 글 → 갈래·형태 프롬프트·덮어쓰기 값)

범위: `git diff 4f63bd0..6bc8184` (브랜치 claude/g73-resay). 코드는 고치지 말고 지적만 한다.
읽을 것: AGENTS.md, docs/design-backbone.md, docs/decisions.md 맨 끝의 G73 절·D12 반박 판정·CP13a 구현 판정(G73-i~l).

찾을 것:
1. 작업 원칙 위반: LLM·번역 모델이 프롬프트·값 경로에 들어감, 허용 슬롯(form.type 갈래, mist.density, layout.proportions, material.opacity, material.emission) 밖 값이 나옴, 원문 charSpan으로 거슬러 가지 않는 프롬프트 낱말, 감정·감각·위기어가 프롬프트에 들어감, 위기 판정 뒤 모델 호출, 끈 설정(`resay = false`)에서 기존 출력·동작 변화.
2. 버그: 갈래 판정 오류, 부정·비유(G71) 처리 누락, fail closed가 아닌 경로(판정 불가인데 생성), 결정성 깨짐(dict 순서·집합 순회·환경 의존), 사람 닮은 사물·동물 차단 구멍, 다의어 2/3개 처리.
3. 빠진 시험.

이미 알고 있는 것(다시 지적하지 말 것): WordNet을 첫 뜻만 보는 것(G73-i, 의도), 빛 갈래의 glowing 기본(G73-l, 의도), venv에 nltk 없음, 실제 대역 사전 데이터 없음(라이선스 확인 전), AGENTS.md 문구 미수정(CP13b), UI·스키마·서버 연결 없음(CP13b), `test_differentiation` 기존 실패 1건, 「공이에요」 Kiwi 분할 문제, test_selection_flow 메모리 문제.

한국어, 지적마다 [높음/중간/낮음], 파일:줄, 재현 입력, 고칠 방법. 60줄 이내.
