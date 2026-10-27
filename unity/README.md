# unity — VR 앱 (예정)

VR 세션(스토리보드 「P07의 25분」의 안전 기지 → Find → Focus → 렌더 → 보정 → Feel toward → 컨테인먼트)을 만들 Unity 프로젝트 자리입니다. 계획된 스택은 Unity XRI + Quest 3입니다(노션 「인터렉션 디벨롭」).

이 폴더에서 쓸 약속은 모두 `shared/`에 있습니다.

| 필요한 것 | 어디서 |
| --- | --- |
| 오프닝·위치 질문·머물기·Feel toward·컨테인먼트 고정 문구 | `shared/protocol/elicitation_protocol.v1.json` (`fixedPhrases`, `vrStages`) 또는 `GET /api/protocol` |
| 면담 진행(챗봇 조건) | `shared/api/README.md` — `POST /api/sessions/{id}/reply` 등 |
| VR 단계 발화의 안전 검사 | `POST /api/guard/check` — `soft`면 [계속][그만], `crisis`면 즉시 중지 |
| 장면 속성 | 확정 텍스트의 추출 결과(`log.extraction.sceneSpecDraft`). 정식 IFSSceneSpec 필드 정렬은 아직 남은 작업 |
| 보정·거리 기록을 세션 로그에 묶기 | `POST /api/sessions/{id}/events` |

지킬 것:
- VR 단계에서는 LLM을 부르지 않습니다(고정 문구와 VR만). beFriend·Fears는 범위 밖입니다.
- 조건 A(조절 가능) / B(고정 제시)는 유도 조건 1·2와 다른 축입니다. 로그에는 `control: adjustable | fixed`처럼 다른 이름을 씁니다.
- 손바닥 펴기(중단), 거리 즉시 리셋, 환경 밝기 올리기, 컨테이너에 담기를 안전장치로 둡니다.
