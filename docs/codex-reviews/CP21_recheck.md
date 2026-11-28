| # | 상태 | 근거 |
|---|---|---|
| 1 | **고쳐짐** | 대상 명사구의 재질 검사는 마지막 낱말에도 적용됩니다. `marble`은 재질 목록, `cave`는 배경 목록에 있어 기각됩니다. [prompts.py](<repo>/tools/gen3d/prompts.py:713), [shape_english_rewrite_block.v0.json](<repo>/shared/lexicon/shape_english_rewrite_block.v0.json:13) |
| 2 | **일부** | 생성기 재검증에 부정, 과거·전언·가정, 비유, 단계, 규칙 문맥 제외, 매퍼가 쓴 구간과 제외 구간 검사가 추가됐습니다. 서버 문맥 판정 함수들을 호출해 판정을 공유합니다. 다만 재검증 코드는 별도로 짜여 있어 서버 검증 전체와 동일하다고 볼 수는 없습니다. [prompts.py](<repo>/tools/gen3d/prompts.py:960), [llm_rewrite.py](<repo>/chatbot/ifs_chatbot/llm_rewrite.py:157) |
| 3 | **고쳐짐** | 원시 출력 전체를 자르지 않고 기록하고 SHA-256도 저장합니다. [llm_rewrite.py](<repo>/chatbot/ifs_chatbot/llm_rewrite.py:419) |
| 4 | **고쳐짐** | 예열은 본 호출과 분리된 요청이며 입력은 고정 문자열 `.`입니다. 기록에도 별도 `contextPrime`으로 남습니다. [llm.py](<repo>/chatbot/ifs_chatbot/llm.py:159), [llm_rewrite.py](<repo>/chatbot/ifs_chatbot/llm_rewrite.py:401) |
| 5 | **고쳐짐** | 중복 인용에서 틀린 `charSpan`은 기각하고, 두 번째 인용을 정확히 가리키면 채택하는 시험과 참여자 보기의 영어 프롬프트·경로·세션 ID 노출 점검이 추가됐습니다. [test_g85_rewrite.py](<repo>/chatbot/tests/test_g85_rewrite.py:576), [test_g85_rewrite.py](<repo>/chatbot/tests/test_g85_rewrite.py:584) |
| 6 | **일부** | 몸 낱말 검사는 규칙 프롬프트 관문 한 곳에서 실행되며, 표준 흐름에서는 이 관문이 G82·G85 호출 전에 차단합니다. 생성기 재검증도 같은 함수에 도달합니다. 차단 시 `blockReason`이 설정되어 중립 형태로 가지 않습니다. 다만 G82·G85 **개별 검증 함수 안에** 이 검사가 들어간 것은 아닙니다. [prompts.py](<repo>/tools/gen3d/prompts.py:863), [prompts.py](<repo>/tools/gen3d/prompts.py:1148), [selection.py](<repo>/chatbot/ifs_chatbot/selection.py:1100) |
| 7 | **고쳐짐** | 근거 꾸밈의 용언 존재·주어·대상 연결 판정은 서버와 생성기 모두 `rewrite_detail_attach_reason`을 호출합니다. [llm_rewrite.py](<repo>/chatbot/ifs_chatbot/llm_rewrite.py:203), [prompts.py](<repo>/tools/gen3d/prompts.py:1004) |
| 8 | **고쳐짐** | 제외 사유 중 정확히 `mapper_unmapped:shape`만 근거 꾸밈에서 열어 둡니다. 다른 제외 사유는 생성기와 서버 양쪽에서 계속 차단합니다. [llm_rewrite.py](<repo>/chatbot/ifs_chatbot/llm_rewrite.py:51), [prompts.py](<repo>/tools/gen3d/prompts.py:987) |

### 새로 찾은 문제

**중간 — G85 생성기 재검증이 서버 검증보다 덜 엄격합니다.** 대상·근거 span을 다시 확인할 때 생성기 측 `_rewrite_head`는 영어 규칙과 인용 일치 등을 검사하지만, 서버가 수행하는 WordNet 금지·장소 상위어 판정은 다시 하지 않습니다. 서버 채택 결과가 보통 먼저 검사되더라도, 생성기 경계에서 같은 검증을 보장한다는 취지에는 미흡합니다. [prompts.py](<repo>/tools/gen3d/prompts.py:796), [llm_rewrite.py](<repo>/chatbot/ifs_chatbot/llm_rewrite.py:250)

- **재현 입력:** 서버 검증을 거치지 않고 생성기에 `subject.en="pond"`와 원문 일치 인용 span을 직접 전달. 생성기 `_rewrite_head`의 자체 검사만으로는 WordNet 장소 판정이 적용되지 않습니다.
- **수정 방향:** 생성기 재검증에서 서버와 같은 WordNet 판정 함수를 호출하거나, 검증 결과의 판·digest를 입력 계약으로 확인해 불일치 시 거부하십시오.

읽기 전용으로 확인했으며, 시험은 실행하지 않았습니다. 설정 파일과 `chatbot/logs/`는 열지 않았습니다.