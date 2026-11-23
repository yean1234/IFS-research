# 모양어 → 모양 모형 (Unity)

참여자가 말한 모양어(동그랗다, 네모, 납작하다, 뾰족하다 …)를 Unity 모형으로 옮기는 규칙입니다. 지금까지는 모양어를 알아보고도 모든 형상을 구 하나(기본 절차 모형)로만 그렸습니다. 이 문서의 변경으로 모양어 네 가지가 모형에 반영됩니다.

- 파이썬 매핑·채점기·spec 형식은 바꾸지 않았습니다. 모양어는 지금처럼 spec의 `_unmapped`(category `shape`, `reason: no_scene_param`)에 남고, Unity가 그 목록을 읽어 모형을 고릅니다.
- 사전과 규칙만 씁니다(LLM 없음, AGENTS.md 1). 같은 spec이면 언제나 같은 모형이 나옵니다.
- 참여자가 말하지 않은 모양을 만들지 않습니다(AGENTS.md 2). 표에 없는 모양어를 구로 바꾸지 않고, 적용하지 못한 모양어는 경고와 기록으로 남깁니다.

코드: `unity/Assets/IFS/Runtime/SceneSpec/ShapeMapping.cs`(표·판정), `ConeMesh.cs`(원뿔 메시), `Runtime/Loading/ShapeModelFactory.cs`(모형 만들기), `SceneLoader.cs`(적용·기록), `Editor/ShapePrefabMenu.cs`(메뉴). 검증: `docs/validation/shapes/README.md`.

## 표

| 1층 사전 낱말(lemma, 품사) | 모양 값 | 모형 | 모양 |
| --- | --- | --- | --- |
| 둥글(VA) · 동그랗(VA) | `round` | Sphere | Unity 기본 구, 지름 1 |
| 네모(NNG) · 네모나(VA) | `square` | Cube | Unity 기본 큐브, 한 변 1 |
| 납작(XR) · 평평(XR) | `flat` | FlatCylinder | Unity 기본 원기둥(지름 1, 높이 2)의 자식을 Y 0.2배 → 지름 1, 두께 0.4 |
| 뾰족(XR) | `pointed` | Cone | 코드로 만든 원뿔: 밑면 지름 1, 높이 1, 48조각, 밑면 뚜껑 있음 |

- 낱말은 `shared/lexicon/layer1_lexicon.v0.json`에서 이 네 값을 가진 항목 전부입니다. v1 오버레이(`layer1_lexicon.v1.json`)에는 모양 항목이 더해지거나 빠진 것이 없어 v0·v1 매핑이 같은 낱말을 씁니다.
- `동그라미`(`circle`)는 `round`가 아니라 별도 값이라 표에 없습니다.
- 모양 모형은 기본 절차 모형과 같은 기본 크기(`SceneLoader ▸ Placement ▸ Primitive Base Size`, 0.35 m)로 줄여 놓습니다. 그래서 `layout.size`의 뜻(0.5 = ×1)이 기본 모형과 같습니다. 그 위에 `layout.size` 배율과 `form.posture` 크기 변형이 똑같이 곱해집니다.

## 규칙

1. **표에 있는 값만 모형으로 바꿉니다.** `_unmapped`에서 `category == "shape"`인 항목을 `charSpan` 순서로 봅니다. 표에 있는 모양어(round·square·flat·pointed) 가운데 처음 나온 것을 적용합니다.
2. **같은 모양을 또 말하면** 그 낱말도 `applied`입니다. **다른 표 모양이 또 나오면** 적용하지 않고 `conflict`로 기록하고 경고합니다.
3. **표에 없는 모양어**(아래 목록, 처음 보는 값 포함)는 구로 바꾸지 않습니다. Console에 경고(파일·세션, 모양 값, 트리거 낱말, `charSpan`)를 내고 `unmapped_shape`로 기록합니다. 모형은 모양 정보가 없을 때 만들던 것 그대로입니다(`form.type`에 따른 기본 모형).
4. **`form.type`과의 관계.** spec의 `form.type`이 `null`(말하지 않음)이거나 `blob`일 때만 모양 모형으로 바꿉니다. spec이 `mist`·`shell`·`fragments`를 말했으면 그 형태 모형을 지키고, 표 모양어는 `not_applied_form`으로 기록하고 경고합니다.
5. **맨 위 상태(`shape.status`).** 모양을 적용했으면 `applied`(표에 없는 낱말이 같이 있어도). 적용하지 않았고 표에 없는 낱말이 하나라도 있으면 `unmapped_shape`. 표 모양어가 형태 때문에만 막혔으면 `not_applied_form`. 모양어가 없으면 `none`. 형태 때문에 막힌 낱말과 표에 없는 낱말이 함께 있으면 맨 위는 `unmapped_shape`이고, 낱말별 상태는 `words`에 둘 다 남습니다.
6. **프리팹이 없을 때.** 모양에 맞는 프리팹이 SceneLoader에 연결되지 않았으면, 메뉴가 프리팹을 만들 때 쓰는 같은 함수(`ShapeModelFactory.Create`)로 같은 형상을 코드로 만들고 경고(「모양 프리팹이 연결되지 않아 같은 형상을 코드로 만듦」)를 남깁니다. 구로 대신하지 않습니다. 기록에는 `viaPrefab: false`로 남습니다.
7. **참여자 조정 중.** 참여자가 `form.type`을 처음 값에서 바꾸면(`SetCategory`) 그 형태 모형을 보여 줍니다. 처음 값으로 돌아오면 모양 모형도 돌아옵니다. 모양 자체를 조정하는 입력은 없습니다.
8. **수치 값은 바뀌지 않습니다.** 모양어는 모형만 고릅니다. `params`·`defaultsUsed`(적용값)는 모양어가 있든 없든 같습니다.
9. **기본 형상(D6, spec 2.2.0)이 있을 때.** spec의 `form.base`가 승인된 기본 형상이고 `form.type`이 null·blob이면 모양 모형으로 바꾸지 않고 모든 모양어를 `not_applied_base`로 기록합니다(경고 아님 — 표에 없는 모양어도). 맨 위 상태는 형태·표 없음보다 뒤 순위의 `not_applied_base`. 기본 형상 경로는 아래 「기본 형상 경로·후보 단계와의 관계」.

## 재질

모양 모형도 IFS 셰이더(`IFS/SceneSpec Opaque`, 반투명이면 `Fade`)를 씁니다. 색·밝기·거칠기·불투명도·침식이 기본 모형과 똑같이 반영됩니다.

IFS 셰이더는 정점을 노이즈로 밀어 덩어리 굴곡과 잔요철을 만듭니다. 큐브·원뿔 같은 각진 메시는 모서리 정점이 면마다 따로라, 밀면 면 사이가 벌어지고 윤곽이 흐려집니다. 그래서 셰이더에 `_Displacement`(정점 변위 전체에 곱하는 값, 기본 1)를 더했고, 로더는 모양 모형에서만 이 값을 0으로 둡니다. 굴곡(`_Lumpiness`)·안개 가장자리(`_Fuzz`)·껍질 열림(`_ShellOpen`)도 0입니다. 기본 모형(blob·mist·shell·fragments)은 이 값을 건드리지 않아 기본값 1 그대로이고, 렌더 결과가 이전과 같습니다(held-out 40개 spec에서 평균 색·덮인 화소 수 동일, `docs/validation/shapes/README.md`).

## 기록

| 어디 | 필드 |
| --- | --- |
| `initialScene.json`(`ExperimentRecorder`) | `shape` |
| 배치 캡처 `report.json`(`BatchCapture`) | `specs[].shape`, `summary.shapes`(상태별·모형별 수, 표에 없는 값별 낱말 수와 spec), `shapePrefabs`(연결된 프리팹 경로) |
| Console · `notes` | 적용한 모양(로그), 적용하지 못한 낱말(경고), 프리팹 없음(경고) |

`shape`의 모양(H27.v0, 낱말 일부만 옮김):

```json
"shape": {
  "status": "applied",
  "applied": "flat",
  "model": "FlatCylinder",
  "viaPrefab": true,
  "formType": null,
  "words": [
    {"shape": "sheet", "lemma": "판", "trigger": "판", "charSpan": [4, 5], "status": "unmapped_shape"},
    {"shape": "flat", "lemma": "평평", "trigger": "평평해요", "charSpan": [57, 61], "status": "applied"}
  ]
}
```

- `status`: `applied` | `none` | `unmapped_shape` | `not_applied_form`
- `applied`·`model`: 적용한 모양 값과 모형. 적용하지 않았으면 `null`
- `viaPrefab`: 프리팹으로 만들었으면 `true`, 코드로 만들었으면 `false`, 적용하지 않았으면 `null`(기본값과 미지정을 섞지 않음)
- `formType`: spec이 말한 `form.type`(말하지 않았으면 `null`)
- `words[].status`: `applied` | `conflict` | `unmapped_shape` | `not_applied_form`, `charSpan` 순서

## 메뉴 IFS ▸ Create Shape Prefabs

1. `Assets/Prefabs/Shapes/`에 프리팹 4개(`Sphere` · `Cube` · `FlatCylinder` · `Cone`), 원뿔 메시 `Cone.asset`, 머티리얼 `ShapeIFS.mat`(IFS 불투명 셰이더, 변위 0)을 만듭니다.
2. 프리팹 루트는 빈 GameObject(크기 1, 1, 1)이고, 메시·렌더러·콜라이더는 자식 `mesh`에 있습니다. 배율(납작 원기둥의 Y 0.2)은 자식에만 둡니다. 디자이너가 모형을 바꿀 때 루트 크기를 건드리지 않아도 됩니다.
3. 열린 씬과 `Assets/IFS/Scenes/SceneSpecExamples.unity`의 모든 SceneLoader ▸ *Shape Prefabs*에 연결하고 씬을 저장합니다. 이름 없는 새 씬은 연결만 하고 저장하지 않습니다(경고).
4. 다시 실행하면 같은 경로·같은 GUID로 덮어씁니다. 두 번 실행한 결과 파일이 바이트 단위로 같았습니다.

- 배치모드: `Unity.exe -batchmode -projectPath unity -executeMethod IFS.SceneSpec.EditorTools.ShapePrefabMenu.CreateShapePrefabsBatch -logFile <로그>`(`-quit` 없이, 끝나면 종료 코드 0/1).
- 배치 캡처(`BatchCapture`)는 로더를 코드로 만들므로, 같은 폴더의 프리팹을 `AssetDatabase`로 읽어 연결합니다. 폴더가 없으면 규칙 6대로 코드로 만들고 `viaPrefab: false`가 됩니다.
- 예시 씬 다시 만들기(IFS ▸ SceneSpec ▸ 예시 테스트 씬 다시 만들기)도 프리팹이 있으면 연결합니다.
- 프리팹 모형을 다른 에셋으로 바꿀 수 있습니다. 렌더러 머티리얼이 IFS 셰이더가 아니면 색·밝기 등은 `SceneLoader ▸ Shader Params`의 대체 프로퍼티로만 반영됩니다(기본 모형 프리팹과 같은 규칙).

## 아직 모형이 없는 모양 값

1층 사전(v0)의 모양 값 가운데 아래는 모형이 없습니다. 나오면 규칙 3대로 경고·기록만 합니다.

| 모양 값 | 사전 낱말 | held-out 60개에서 |
| --- | --- | --- |
| `dot` | 점 | 6 |
| `edge` | 가장자리 | 6 |
| `thin` | 얇 | 6 |
| `thread` | 실 | 4 |
| `hollow` | 비 | 2 |
| `long` | 길 | 2 |
| `sharp` | 날카롭 | 2 |
| `sheet` | 판 | 2 |
| `angular` | 각지 | 0 |
| `boundary` | 경계 | 0(H28 v0·v1에 부정형으로 나오지만 `_negated`라 읽지 않음) |
| `bumpy` | 울퉁불퉁 | 0 |
| `circle` | 동그라미 | 0 |
| `elongated` | 길쭉 | 0 |
| `hole` | 구멍 | 0 |
| `knot` | 매듭 | 0 |
| `line` | 선 | 0 |
| `string` | 끈 | 0 |
| `thick` | 두껍 | 0 |
| `triangle` | 세모 | 0 |

## 기본 형상 경로·후보 단계와의 관계 (2026-11-23)

RQ V4 실험 프로토타입(`docs/prompts/prototype-v4-build.md`)에서 두 가지가 더해졌습니다. 상세는 `docs/scene-spec-mapping.md` 7절입니다.

### 형상 명사 → 범주 → 기본 형상 (`form.base`) — 구현(D6, 2026-11-23, G30)

이 문서의 **모양어 → 모양 모형** 경로와 다른 경로입니다. 매퍼 v2(builder 2.2.0)와 스키마 2.2.0에서만 나옵니다(v0·v1 출력 불변).

| | 모양어 → 모양 모형 | 형상 명사 → 범주 → 기본 형상 |
| --- | --- | --- |
| 입력 낱말 | 모양 형용사·명사(둥글·네모·납작·뾰족) | 형상을 이름 붙이는 명사 34개(그릇·유리병·상자·실·실타래·매듭·종이·천·막·불꽃·촛불·물방울 …, `shared/lexicon/base_shapes.v1.json`, 초안) |
| spec에서 | 슬롯 없음. `_unmapped`(category `shape`)를 Unity가 읽음 | 슬롯 `form.base` + `form.baseVariant`, `_provenance`와 함께 |
| 모형 | Sphere·Cube·FlatCylinder·Cone | 절차 메시 `container/1`·`line/1`·`sheet/1`·`flame/1`·`drop/1`(`Runtime/Rendering/BaseShapeMesh.cs`) |
| `form.type`과 | 비었거나 blob일 때만(규칙 3) | 비었거나 blob일 때만 그림. mist·shell·fragments면 그 형태를 그리고 base는 `not_applied_form` |
| 둘이 함께 나오면 | 모양어는 **`not_applied_base`**(새 상태, 경고 아님) — 모형이 있든 없든 기본 형상이 윤곽을 정함 | 기본 형상이 앞섬. 예외: '네모난 상자·그릇'의 '네모'는 매퍼가 `form.baseVariant.profile = square`로 넣음 |
| 변형본 | 소유감 변형본이 모양 모형을 강제하면(`shapeModel`) | 그 모형이 앞서고 base는 `not_applied_forced` |

- 기본 형상 목록은 "IFS가 정한 범주"가 아니라 "문헌을 참고해 연구팀이 정한 목록"입니다(G6).
- **사전에 없는 명사**는 지금처럼 `_unmapped`에 category `unlisted_noun`으로 남고 `form.base`는 null입니다(대신할 형상을 고르지 않음). 그리지 않기로 한 낱말(사람·아이, 공격하는 존재, 무기, 죽음·외상, 피·올가미)은 reason `excluded_shape`로 남습니다.
- 조절에서 기본 형상을 지우면(`form.base` = none) 그 spec의 모양어가 모형이 되지는 않습니다(로드 때 `not_applied_base`로 판정해 모형을 정하지 않았기 때문). blob으로 그려집니다.

### 후보 선택·조절 단계에서

- **기본 형상(D6)을 말했으면 형태 자리는 '말함'입니다.** 기본 형상은 후보 값으로 내밀지 않습니다. 조절의 "형태" 항목은 form.type 4값 + 기본 형상 5값입니다(`candidate_values.v2.json`). 아래 G32 규칙은 기본 형상이 그려지지 않는 spec에만 걸립니다 — builder 2.1.0까지 모형 없는 모양어였던 '실'·'선'·'끈'·'매듭'·'판'은 이제 기본 형상의 근거라 G32 경로를 타지 않습니다.
- **모양어를 말했으면 형태 자리를 '말함'으로 봅니다.** 후보 생성기는 `_unmapped`에 category `shape` 항목이 있으면 `form.type`이 null이어도 형태 축을 벌리지 않습니다(`chatbot/tests/test_candidates.py::test_shape_word_counts_as_said_form`). 형태 후보로 mist 등을 내밀면 규칙 4 때문에 말한 모양 모형이 그려지지 않게 되기 때문입니다.
- 이 규칙은 **표에 없는 모양어**(실·선·판·점 …)에도 똑같이 걸립니다. 그런 말은 모형이 없어 기본 모형으로 그려지는데, 형태 후보도 나오지 않습니다(예: 합성 문장 "가는 실 같은 게 손목에 감겨 있어요" → 후보 축은 크기·투명도). 참여자는 조절 단계의 "형태"에서만 형태를 바꿀 수 있습니다. 내부 시스템 점검에서 볼 항목입니다(`docs/internal-trial-guide.md`).
- (D6 전) 조절의 "형태" 항목은 `form.type` 네 값뿐이었습니다. 모양 모형을 직접 고르는 항목은 지금도 없고, 챗봇은 덮어쓰기에 `shapeModel` 키를 쓰지 않습니다. 형태 덮어쓰기와 모양 모형 규칙이 Unity에서 어떻게 겹치는지 보는 교차 테스트는 아직 없습니다(`docs/validation/selection-flow/README.md` 10절).
- 속성 출처 네 가지(말함/고름/고침/기본값)는 spec이 아니라 선택 기록 `selection.json`에 적습니다(G15). 모양 모형은 지금 출처 칸이 없고 Unity 기록의 `shape`에만 남습니다.

## 한계

- **부분을 말한 모양어도 전체에 적용합니다.** 「끝이 뾰족해요」처럼 물체의 한 부분(끝·모서리·가장자리)을 말한 모양어도 모형 전체를 원뿔로 바꿉니다. 매핑은 그 모양어가 전체를 말하는지 부분을 말하는지 `_unmapped`에서 구별하지 않습니다.
- **파이썬 쪽 기록은 그대로입니다.** spec의 `_unmapped[].reason`은 여전히 `no_scene_param`이고, 모양어가 모형에 반영됐는지는 Unity 기록(`shape`)에만 있습니다. 채점기의 `unsupportedRate` 등 E2E 지표(`docs/validation/e2e/`)는 이 변경 전에 계산한 값이고, 모양 모형을 고려하지 않습니다.
- **자세 변형이 모양 위에 겹칩니다.** `form.posture`의 크기 변형이 모양 모형에도 곱해집니다. 예: H27은 「평평해요」로 원판이 됐지만 `posture = hanging`(y × 1.25)이 겹쳐 두께 0.5 : 지름 0.9로, 원판보다 깡통에 가깝게 보입니다.
- **원판 두께.** Unity 원기둥은 높이가 2라 Y 0.2배의 결과는 두께 0.4(지름의 0.4배)입니다. 더 얇게 하려면 프리팹 자식의 Y 배율을 바꾸면 되지만, 그때는 이 문서와 테스트(`ShapeModelTests`)도 함께 고칩니다.
- **round는 기본 모형과 윤곽이 비슷합니다.** 기본 모형도 구를 노이즈로 민 덩어리라, round가 바꾸는 것은 주로 굴곡이 없어진다는 점입니다.
- **모양 크기는 기본 모형과 같습니다.** 모양 모형은 지름 1 모형을 0.35 m로 줄여 놓습니다. 형태 프리팹(Form Prefabs)이 프리팹 자체 크기(×1)를 쓰는 것과 다릅니다.
- **모양은 로드 때 한 번 정합니다.** 기록도 `initialScene.json`에만 있습니다. 참여자가 모양을 직접 바꾸는 조정 입력은 없습니다.
- **부정·맥락 표현은 읽지 않습니다.** `_negated`(「경계가 없어요」), v1의 `_context`·`_parts`에 있는 모양어는 모형에 쓰지 않습니다.
