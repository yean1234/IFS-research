# 매핑 v2: 사전에 없는 명사 기록(D1)과 형상이 사라지는 오류 수정(D2)

> **개발 자료에서 잰 수치입니다.** v2 규칙은 dev 코퍼스(`chatbot/tests/fixtures/imagery_corpus/dev.json`)와 목업 코퍼스(`docs/validation/mock-forms/mock_corpus.json`)를 보면서 만들었습니다. 둘 다 이미 본 합성 자료라서 아래 수치로 v2가 일반화된다고 말할 수 없습니다. held-out 코퍼스는 열지도, 돌리지도 않았습니다(X13·X29).
> **합성 데이터입니다.** 모든 문장은 AI가 쓴 합성 대사입니다(AGENTS.md 6). 정답 라벨과 채점 규칙도 AI가 만들었습니다.

작업일 2026-11-23, 브랜치 `claude/prototype-v4-build`. 근거 문서는 `docs/prompts/prototype-v4-build.md` 단계 D(D1·D2), `docs/validation/mock-forms/README.md` 6·7절, `docs/mapping-audit.md` A06·A14입니다.

## 1. 무엇을 바꿨나

| 파일 | 내용 |
| --- | --- |
| `chatbot/ifs_chatbot/scene_builder_v2.py` | 새 매핑 v2. `SceneSpecBuilderV1`을 상속하고, 바뀌는 메서드만 다시 씁니다(`_scope`·`_lexicon_cands`·`_measure_dimension`·`_ref_noun`·`_merge`, 그리고 `build` 뒤에 D1 명사 기록) |
| `shared/lexicon/scene_params.v2.json` | v2 규칙과 수치, 그리고 근거(새 파일) |
| `shared/lexicon/noun_stoplist.v2.json` | D1 불용 명사 251개, 6개 묶음별 근거(새 파일) |
| `chatbot/ifs_chatbot/scene_spec.py` | `is_mapping_fallback()` 추가(아래 4절) |
| `chatbot/ifs_chatbot/controller.py`·`config.py` | `mapping.mode = "v2"`로 고를 수 있게 함. **기본값 v1은 그대로**이고, v2 빌더는 v2를 요청할 때만 만듭니다 |
| `chatbot/ifs_chatbot/eval/corpus_run.py`·`fidelity.py`·`e2e.py` | `--mapper v2` 선택, 대체 판정에 `is_mapping_fallback()` 사용 |
| `chatbot/tests/test_scene_builder_v2.py` | 새 테스트(65개, 매개변수 포함) |

v0·v1의 코드와 설정 파일(`scene_builder.py`·`scene_builder_v1.py`·`*.v0.json`·`*.v1.json`)은 고치지 않았습니다. 확인한 내용은 다음과 같습니다.
- v0 sha256 고정 테스트를 통과합니다.
- v1 출력은 목업 확인 때 커밋한 `docs/validation/mock-forms/specs/v1/` 36개와 바이트까지 같습니다(`test_v1_mock_specs_unchanged`).
- v1 수치는 목업 README 3절 값(반영 0.765 · 왜곡 0.06 · 손실 0.01)과 같습니다.

## 2. 규칙

### D1 사전에 없는 명사

다음 조건을 모두 만족하는 명사를 `_unmapped`에 남깁니다.

1. Kiwi 품사가 NNG 또는 NNP입니다.
2. 1층 사전(v0 + v1 오버레이, 모든 범주의 표제어와 이형 562개)에 없습니다.
3. 값 근거(`_provenance`)와 다른 보존 기록(`_unmapped`·`_negated`·`_alternatives`·`_context`·`_parts`·`_measurements`·`_direction`·`_needsConfirmation`)이 덮지 않았습니다.
4. 불용 명사가 아닙니다. 불용 명사는 모두 326개입니다. 파일에 적은 251개(신체 부위·시간·장소 일반어·기능·차원·감정 명사)에, v1 표에서 가져온 부분 명사·위치 명사·차원 주제·상황 명사·때 표지·단위 75개를 더한 수입니다.
5. 바로 뒤에 -하다(XSV·XSA)가 붙지 않았습니다. '퇴근하고' 같은 서술성 명사는 빠집니다.

띄어 쓰지 않고 붙은 명사가 모두 조건을 만족하면 하나로 묶습니다.

기록 형식은 아래와 같습니다. `category`는 스키마가 자유 문자열로 두는 칸이라 새 값을 썼습니다. `reason`과 `_provenance.source`는 스키마 enum에 맞는 값이 없어서 가장 가까운 값을 넣었습니다(6절).

```json
{"lemma": "화분", "category": "unlisted_noun", "reason": "no_scene_param",
 "value": {"noun": "화분", "role": "subject", "scope": "main"},
 "_provenance": {"source": "phrase_rule", "trigger": "화분", "charSpan": [9, 11], "rule": "unlistedNoun.화분"}}
```

- `role`은 뒤에 붙은 조사로 정합니다. 값은 subject(이/가/은/는), named(-이에요, -요, 명사로 끝남), location(처소 조사, 뒤에 오는 위치 명사), object, modifier, other 중 하나입니다.
- `scope`는 맥락 명사와 형상 명사를 가르는 값입니다. 다음 중 하나에 해당하면 `context`, 아니면 `main`입니다.
  - v1 회상 문장
  - '연락이 끊긴 일이요'처럼 관형형 + 상황 명사로 끝나는 문장
  - '생각나다'·'기억나다'·'떠올리다'가 있는 문장
  - 상황·시간 명사가 있고 슬롯 값이 하나도 나오지 않은 문장('주말 아침 산책이요')
  - '소파에 누웠을 때'처럼 관형형 + 때·적·순간·동안 앞에 오는 명사
- **'작은 화분'에서 크기가 빠진 원인**: '화분'이 v1 배경 사물 목록 `backgroundNouns`(`scene_params.v1.json`)에 들어 있습니다. 그래서 v1 `_scope`가 '작은'을 배경 사물의 속성으로 보고 `_context`(reason `background_object`)로 보냈습니다. 배경 사물 낱말이 형상 자체일 때를 가리지 못하는 규칙 결함입니다. v2에서는 배경 사물 낱말이 '있다'·'생기다'·'놓이다'의 주어이고, 같은 절에 다른 배경 처소어('창가에')가 없으면 형상으로 봅니다. 그 결과 '가슴 앞에 작은 화분이 있어요'의 크기가 0.316이 됩니다. '창가에 화분이 있어요. 화분은 작아요'와 '방은 어두운데 그것은 밝아요'는 v1과 같습니다.

### D2 형상이 사라지거나 눈앞을 가리는 오류

| | 고른 방법 | 값과 근거(`scene_params.v2.json`) |
| --- | --- | --- |
| (a) '거의 투명'·'투명에 가까운' | 0 대신 작은 양수를 줍니다. '투명에 가까운'의 '가깝'은 거리로 쓰지 않습니다 | `nearlyTransparent` 0.15. '투명' 0.1보다 덜 투명하고, Unity 러너의 lowVisibility 경고 기준(유효 opacity 0.15 미만)과 같은 값입니다 |
| | '완전히·완전·아예 투명' | 말한 대로 0.0입니다(원칙 2). 안 보이는 것은 참여자가 말한 결과입니다 |
| | '아주 투명' 등 그 밖의 강한 정도 부사 | 하한 0.05('투명'의 절반)를 둡니다 |
| | '반쯤 투명'(A14) | 0.5(반투명)입니다 |
| | 부분 한정('끝은 거의 투명'·'가장자리는 투명', A06) | `material.opacity`를 부분 한정 슬롯에 넣었습니다. 테두리·끝(detail)과 안쪽(inner)만 말한 투명도는 전체 값으로 쓰지 않고 `_parts`에 남깁니다. 단 '속이 비쳐요'는 형상 전체가 비친다는 뜻이라 v1처럼 전체 값으로 둡니다(dev D02·D16이 근거) |
| (b) 거리 0 | **하한 + 다시 읽기를 함께 썼습니다.** 하한은 `distance.floor` 0.1(약 0.57 m)입니다. 사전의 '코앞'(very_near)과 같은 값이라, v1이 이미 '가장 가깝다고 말한 거리'로 쓰고 있습니다. 말한 원래 값은 rule 끝의 `+floor(0.1)`과 `_measurements`에 남습니다 | 신체 부위에 '붙어'는 머리와의 거리가 아니라 몸 위치이므로 distance를 채우지 않고 `_unmapped`(category distance)에 남깁니다. 판정 순서는 이렇습니다. ① 같은 절에 '부위(+쪽)+에'나 '저한테'가 있으면 몸입니다. ② 다른 처소어('얼굴 앞에')가 있으면 거리로 읽고 하한을 적용합니다. ③ 처소어가 없고 텍스트에 신체 부위가 있으면 몸입니다. 또 수치 옆 3토큰 안에 높이 말(위·아래·높이 …)이 있으면 수평 거리가 아니라고 보고, `_measurements`에 dimension unknown으로 남깁니다('머리 위 한 뼘쯤 높이') |
| (c) 자세 | 자세어가 있는 절의 주어와 상황을 규칙으로 판정합니다. 해당하면 `form.posture`에 넣지 않고 `_context`에 남깁니다 | ① 상황절(관형형 + 때 …, -면: '누웠을 때'·'서 있으면')이면 reason `recollection_sentence`입니다. ② 1인칭 주어('제가 서 있는')이면 `background_subject`입니다. ③ 소유자 없는 신체 부위 주어('몸이 … 처져요')도 `background_subject`입니다. 주어가 생략된 경우와 형상이 주어인 경우('작은 사람 모양이 쪼그려 앉아', '그 사람 어깨가 축 처져')에는 v1처럼 형상 자세로 둡니다 |
| (d) '가슴 앞을 덮고' | 신체 부위 바로 뒤의 위치 명사('앞')는 덮음 비교의 기준 사물로 쓰지 않습니다 | v1은 coverObjects '앞'(1.7 m, 시야 전체) 때문에 size가 1.0이 되었습니다(M08). v2에서는 '가슴을 다 덮을 만큼'(0.4 m → 0.667)이 값이 됩니다 |

(d)에서 고치지 않은 것도 있습니다. '아주 작은 것'(손톱·구슬·1 cm → size 0–0.04)은 참여자가 말한 크기를 그대로 옮긴 값입니다. 크기 압축 규칙(`size.octavesPerUnit`)과 렌더러 최소 크기는 설계·Unity 쪽에서 정할 일이라 바꾸지 않았습니다. 형상 사전 낱말 추가(구름·액체·빛)도 범위 밖입니다(G4).

## 3. v1 대 v2 수치(fidelity 채점기, 개발 자료)

`python -m ifs_chatbot.eval.fidelity --corpus <코퍼스> --mapper v1 --compare v2 --out <폴더>`로 냈습니다. 원본은 `score/dev/`와 `score/mock/`에 있습니다(`paired.*`, `report.v1.md`, `report.v2.md`). 구간은 항목 단위 쌍 군집 부트스트랩의 95% 구간입니다.

| 지표 | dev v1 | dev v2 | mock v1 | mock v2 |
| --- | --- | --- | --- | --- |
| 반영률(슬롯 속성) | 0.937 | 0.937 | 0.765 | **0.775** |
| 왜곡률 | 0.000 | 0.000 | 0.060 | **0.045** |
| 손실률 | 0.000 | 0.000 | 0.010 | 0.010 |
| 컨트롤러 탈락률 | 0.063 | 0.063 | 0.070 | 0.070 |
| 보존률(전체 속성) | 0.942 | 0.942 | 0.872 | 0.884 |
| 근거 없는 값 비율 | 0.203 | 0.199 | 0.255 | 0.230 |
| 반영률 차이(v2 − v1) | 0.000 [0.000, 0.000] | | +0.010 [0.000, 0.025] | |
| 왜곡률 차이 | 0.000 [0.000, 0.000] | | −0.015 [−0.032, 0.000] | |

슬롯 값이 달라진 항목은 dev 30개 중 2개, mock 36개 중 9개입니다. `_unmapped`에 사전에 없는 명사가 생긴 항목은 dev 29개(73개 명사, context 42), mock 34개(72개 명사, context 31)입니다. 목업 v2 spec 36개는 `specs/`에 있습니다. 컨트롤러가 쓴 바이트 그대로이며, e2e 결과는 스키마 유효 36/36, 원칙 검사 문제 0, 대체 0, LLM·네트워크 호출 0입니다.

### 슬롯이 달라진 항목

| 항목 | 슬롯 | v1 → v2 | 근거 말 | 채점 상태 변화 |
| --- | --- | --- | --- | --- |
| dev D15 | layout.distance | 0.0 → null | '옆구리 쪽에 … 붙어' (+ '붙어 있어요' 2회) | 근거 없는 값 1개 줄어듦(정답 라벨 없음) |
| dev D20 | layout.distance | 0.0 → 0.1 | '얼굴 앞 30센티쯤' | 반영 → 반영(**말한 30 cm가 약 57 cm로 그려짐**, 아래 5절) |
| M04 | material.opacity | 0.0 → 0.15 | '거의 투명해서' | 반영 → 반영(화면에서 사라지던 값) |
| M08 | layout.size | 1.0 → 0.667 | '가슴 앞을 덮고' → '가슴을 다 덮을 만큼' | 왜곡 → 반영 |
| M09 | material.opacity | 0.1 → 0.5 | '반쯤 투명해서' | 왜곡 → 반영 |
| M12 | material.opacity | 0.0 → 0.15 | '거의 투명하고' | 반영 → 반영(화면에서 사라지던 값) |
| M15 | layout.distance | 0.0 → null | '등에 붙어' | 근거 없는 값 1개 줄어듦 |
| M23 | form.posture | standing → null | '제가 서 있는 자리' | 근거 없는 값 1개 줄어듦 |
| M27 | layout.distance | 0.0 → null | '머리 위 한 뼘쯤 높이' | 근거 없는 값 1개 줄어듦 |
| M31 | form.posture | lying → null | '소파에 누웠을 때요' | 왜곡 → 미반영(원문 보존). 기대값 curled('동그랗게 말려')는 사전에 없어 여전히 못 채움 |
| M35 | form.posture | drooping → null | '몸이 무겁고 처져요' | 근거 없는 값 1개 줄어듦 |

## 4. 스키마와 meta

스키마 `scene-spec.v2.1.json`은 바꾸지 않았습니다. 그래서 다음처럼 기록합니다.
- `meta.mapping.used`가 허용하는 값은 `v0`·`v1`뿐입니다. v2는 `{"requested": "v2", "used": "v1", "fallbackReason": null}`로 적고, `meta.pipeline.builder = "scene-spec-builder-v2/2.0.0"`과 `lexicons.sceneParamsV2`·`lexicons.nounStoplist`로 v2임을 남깁니다.
- 기존 대체 판정(`used ≠ requested`)대로라면 v2가 언제나 '대체'로 잡힙니다. 그래서 `scene_spec.is_mapping_fallback()`을 만들고 corpus_run·fidelity·e2e가 이 함수를 쓰게 했습니다. v0·v1에 대한 판정은 이전과 같습니다.

## 5. 한계와 v2가 새로 틀릴 수 있는 곳

- **거리 하한은 말한 가까운 거리를 늘립니다.** dev D20 '얼굴 앞 30센티쯤'은 v1에서 0(0.3 m, 말한 값 그대로)이었는데, v2에서는 0.1(약 0.57 m)입니다. 채점 범위 안이라 '반영'으로 남았지만 말한 값과 다릅니다. 원래 값은 rule과 `_measurements`에 남아 있습니다. 0.1에서 형상이 시야를 덮지 않는지는 Unity로 확인하지 않았습니다.
- **처소어 없는 '붙어'는 몸에 붙은 것으로 봅니다(판정 ③).** 신체 부위를 말한 텍스트에서 몸이 아닌 것에 붙은 경우('창문에 붙어', 처소어가 다른 절에 있음)도 거리가 비게 됩니다.
- **자세 ③(소유자 없는 신체 부위 주어)는 형상이 사람·동물일 때 틀릴 수 있습니다.** 예를 들어 앞 문장에서 '작은 사람'을 말하고 이어서 '어깨가 처져 있어요'라고 하면 자세가 비게 됩니다. 원칙 2에 따라 채우지 않는 쪽을 골랐습니다.
- **'배경 사물이 형상'이라는 판정은 '있다' 류의 주어일 때만 합니다.** '화분이에요'(명사로 끝나는 답)나 '화분은 작아요'만 말한 경우에는 v1처럼 배경으로 봅니다.
- **scope는 표시일 뿐입니다.** 상황을 이름만으로 말한 첫 답('할머니 댁 마당이 떠올라요'·'비 오는 날 버스 정류장이요'의 정류장 등)은 main으로 남습니다. role·scope는 조사 규칙이라 사람이 판단한 '형상 명사'와 같지 않습니다.
- **스키마 enum 한계.** `_unmapped.reason`에는 '사전에 없음' 값이 없어서 `no_scene_param`을 쓰고, `_provenance.source`에는 '사전 밖'이 없어서 `phrase_rule`을 씁니다. 자세의 `_context.reason`에는 '참여자 자신'이 없어서 `background_subject`(1인칭·신체 부위 주어)와 `recollection_sentence`(상황절)를 씁니다. 스키마를 바꿀지는 메인 세션이 정합니다.
- Unity 캡처는 하지 않았습니다. 화면이 실제로 나아졌는지(M04·M12가 보이는지, M15·M27이 시야를 덮지 않는지)는 `specs/`로 다시 캡처해야 압니다.

## 6. 기본 매핑을 v2로 바꿀 때 영향을 받는 곳

- `chatbot/config/default.toml`·`pilot.toml`의 `[mapping] mode`, 그리고 `ifs_chatbot/config.py`의 `MappingConfig.mode` 기본값
- `controller.py`의 v2 빌더 생성. 지금은 mode가 v2일 때만 만듭니다. strict 처리는 v1과 같습니다
- `_write_variants`의 비교 파일. v2가 있으면 `{sid}.v2.json`이 더해집니다
- 테스트 중 기본 mode가 v1이라고 가정하는 것들입니다.
  - `tests/test_scene_builder_v1.py`: `test_strict_config_keys`, `rt_v1` fixture, `test_v1_*` 대체 테스트, `test_corpus_run_mapper_selection_ignores_config_mode`
  - `tests/test_scene_builder_v2.py`: `test_default_mode_is_unchanged_and_v2_not_built`
  - 세션 로그의 `variants` 키를 보는 테스트
- `eval/e2e.py`의 `DEFAULT_MAPPERS = ("v0", "v1")`
- Unity 예시 `unity/Assets/StreamingAssets/IFS/examples/v1/`는 v1 출력 고정입니다(`test_unity_v1_examples_are_current_v1_output`). v2 예시가 필요하면 따로 만들어야 합니다.
- held-out 수치(반영률 0.698 등)는 v1 기준입니다. v2를 주 매핑으로 쓰려면 규칙을 보지 않은 사람이 쓴 새 평가 문장이 필요합니다(X13).

## 재현

```powershell
cd chatbot
.venv\Scripts\python.exe -m ifs_chatbot.eval.fidelity --corpus tests\fixtures\imagery_corpus\dev.json --mapper v1 --compare v2 --out <임시>\dev
.venv\Scripts\python.exe -m ifs_chatbot.eval.fidelity --corpus ..\docs\validation\mock-forms\mock_corpus.json --mapper v1 --compare v2 --out <임시>\mock
.venv\Scripts\python.exe -m ifs_chatbot.eval.e2e --corpus ..\docs\validation\mock-forms\mock_corpus.json --out <임시>\e2e --no-network --mappers v1,v2
#   → <임시>\e2e\specs\*.v2.json을 specs\로 복사
.venv\Scripts\python.exe -m pytest -q tests\test_scene_builder_v2.py
```
