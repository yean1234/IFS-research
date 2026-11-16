# 합성 spec 렌더 시험 (Unity)

`specs/`의 JSON 4개는 **손으로 쓴 합성 값**입니다. 참여자 데이터도, 챗봇 대사도, 장면 빌더 출력도 아닙니다. 예시 2개(EX01·EX02)가 다루지 않는 형태(mist·fragments·shell)와 고채도 유채색의 렌더·색·성능을 보려고 만들었습니다.

| 파일 | 형태 | 색(HSL) | 재질 |
| --- | --- | --- | --- |
| `SYN-U1_mist.json` | mist | (0.58, 0.2, 0.7) | opacity 0.6 |
| `SYN-U2_fragments.json` | fragments | (0.1, 0.6, 0.5) | roughness 0.6 |
| `SYN-U3_shell.json` | shell | (0.33, 0.4, 0.4) | roughness 0.3 |
| `SYN-U4_red_glossy.json` | blob | (0.0, 0.9, 0.5) | roughness 0.1 |

- `meta.pipeline.builder`는 `handwritten-synthetic/0`, `_provenance`의 `rule`은 `synthetic.handwritten-render-test>…`, `trigger`는 `(합성)`입니다. 원문이 없어 `charSpan`은 [0, 0]이고, `sourceTextHash`는 라벨 문자열(`synthetic unity render test SYN-U? (hand-written, no source text)`)의 SHA-256입니다.
- `meta.pipeline.analyzer`가 `none`이라 `shared/schemas/scene-spec.v2.json`의 열거값(kiwi·fallback-regex)과는 맞지 않습니다(의도). Unity 로더는 이 필드를 검사하지 않습니다. 빌더 출력으로 오해하지 않게 하려고 일부러 남겼습니다.
- 결과: 이 폴더의 `report.json`과 PNG. 다시 만드는 명령과 요약은 `unity/README.md` 「검증 결과」에 있습니다.
