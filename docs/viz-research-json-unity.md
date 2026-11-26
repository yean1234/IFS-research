# Unity에서 JSON으로 형상 시각화하기: 1차 자료, 선행 연구, 한계 (2026-11-26, 웹 조사)

이 문서는 세 질문에 답한다. (1) Unity에서 JSON으로 형상을 시각화한 연구나 공신력 있는 자료가 있는가. (2) Unity는 JSON을 어떻게 받아 시각화하는가. (3) JSON으로 형상을 표현하면 어디까지 되고 어디서 막히는가. 끝 절에서 이 저장소의 IFSSceneSpec에 주는 시사점을 정리한다.

- 코드는 고치지 않았다. 저장소 쪽 사실은 `shared/schemas/scene-spec.v2.2.json`, `shared/lexicon/base_shapes.v1.json`, `docs/shape-mapping.md`, `unity/Assets/IFS/Runtime/{SceneSpec,Loading,Rendering}`을 grep으로만 확인했다.
- glTFast 설치·런타임 API·Built-in 셰이더 포함 문제, USD, 절차형·입자·에셋 대안의 1차 평가는 `docs/gen3d-feasibility.md` 2.1절과 2.4절에 이미 있다. 여기서는 되풀이하지 않고, 필요한 곳에서 그 절을 가리킨다.
- 각 주장 옆에 실제로 연 출처 URL을 붙였다. 검색 결과 요약만 보고 원문을 열지 못한 것은 "(요약만 확인)"으로 표시하고, 끝의 "확인 필요" 목록에 모았다.

## 0. 요약

| 질문 | 답 |
| --- | --- |
| JSON으로 형상을 시각화한 연구가 있나 | 있다. 다만 대부분은 JSON(또는 비슷한 구조화 텍스트)으로 **배치·선택·인코딩**을 기술하고, 형상 자체는 에셋 라이브러리나 코드에서 가져온다. DXR(Unity, Vega-Lite식 JSON)과 VRIA(A-Frame, JSON 문법)는 "JSON 사양 → 해석기 → 3D 마크"가 논문의 핵심 구조다. LLM 장면 생성 연구(Holodeck, LayoutGPT, SceneCraft, 3D-GPT)는 중간 표현을 쓰지만 형상은 에셋 검색이나 절차적 생성기에 맡긴다. LLMR과 DreamCodeVR은 JSON이 아니라 C# 코드를 런타임에 컴파일한다. |
| Unity는 JSON을 어떻게 받나 | JSON은 데이터일 뿐이다. `JsonUtility`나 Newtonsoft Json.NET이 JSON을 C# 객체로 바꾸고, 그 객체를 읽는 C# 코드(해석기)가 `GameObject.CreatePrimitive`, `Mesh` API, 머티리얼, 파티클로 장면을 만든다. 형상 자체를 데이터로 옮기는 표준은 glTF 2.0이다. glTF는 장면 기술을 JSON으로, 정점 같은 기하 데이터를 바이너리 버퍼로 나눠 담는다. |
| 한계는 무엇인가 | 닫힌 어휘(해석기가 아는 키·값만 그린다), 임의 지오메트리를 JSON 숫자 배열로 싣기의 비효율, 매개변수 형상군 밖의 형상은 못 그림, 재질·발광·반투명은 해석기와 셰이더가 지원하는 만큼만 표현된다는 점, 그리고 Quest 단독 실행의 그리기 호출·삼각형·셰이더 비용이다. |

## 1. Unity는 JSON을 어떻게 받아 시각화하는가 (1차 자료)

### 1.1 JSON → C# 객체

| 방법 | 확인한 내용 | 출처 |
| --- | --- | --- |
| `JsonUtility` (엔진 내장) | MonoBehaviour·ScriptableObject 하위 클래스, `[Serializable]` 클래스·구조체를 지원한다. "Unity serializes fields only, not properties." 배열이나 기본형을 최상위로 직접 넘기지 못하고 클래스로 감싸야 한다. JSON에 있는데 클래스에 없는 값은 무시하고, JSON에 없는 필드는 생성자 값이 남는다. 다형성은 내장 지원이 없고, 공통 필드로 먼저 읽어 타입을 정한 뒤 다시 읽는 방법을 권한다. 대신 빠르고 GC 할당이 적다. | https://docs.unity.com/en-us/engine/current/manual/programming-environment/code-reload-serialization/script-serialization/json-serialization |
| Unity 직렬화 규칙 (`JsonUtility`가 따르는 규칙) | 다차원 배열, 가변(jagged) 배열, 컬렉션 안에 바로 든 컬렉션(`List<Dictionary<…>>` 등)은 직렬화하지 않는다. 래퍼 클래스로 감싸거나 `ISerializationCallbackReceiver`를 쓴다. `[SerializeReference]` 없이는 파생 타입이 부모 타입으로 바뀐다(다형성 손실). 간접 순환은 10단계에서 끊고 나머지를 버린다. 현재(6000.6) 문서는 `[SerializeField]`를 붙인 `Dictionary<TKey,TValue>`를 지원 목록에 올린다. 예전 버전에서는 딕셔너리를 직렬화하지 않았으므로 쓰는 Unity 버전을 확인해야 한다. | https://docs.unity.com/en-us/engine/current/manual/programming-environment/code-reload-serialization/script-serialization/rules |
| Newtonsoft Json.NET (`com.unity.nuget.newtonsoft-json`) | Unity가 배포하는 패키지다. 3.2 문서 기준으로 Newtonsoft.Json 13.0.2에 대응하고, 사용법은 Json.NET 문서로 연결한다. 딕셔너리, 다형성, `JObject` 같은 동적 접근, 누락·초과 필드 오류 처리 같은 기능은 Json.NET 쪽 기능이다. | https://docs.unity3d.com/Packages/com.unity.nuget.newtonsoft-json@3.2/manual/index.html (요약만 확인) |

이 저장소는 Newtonsoft를 쓴다. `SceneSpecJson.Parse`는 `MissingMemberHandling.Error`(모르는 키가 있으면 실패), `NullValueHandling.Include`(null을 지우지 않음)로 엄격하게 읽는다(`unity/Assets/IFS/Runtime/SceneSpec/SceneSpecJson.cs`). 모르는 키를 조용히 버리는 `JsonUtility`의 기본 동작과 달리, 스키마 밖 입력을 거부한다. 원칙 2("비어 있는 슬롯은 비어 있다고 표시")와 맞는 선택이다.

### 1.2 C# 객체 → 장면: 해석기가 형상을 만든다

JSON에는 "무엇을 그려라"만 있고 "어떻게 그려라"는 없다. 어떻게는 C# 해석기가 정한다. Unity 공식 문서로 확인한 경로는 다음과 같다.

| 경로 | 확인한 내용 | 출처 |
| --- | --- | --- |
| 프리미티브 | `GameObject.CreatePrimitive(PrimitiveType)`는 MeshRenderer와 맞는 콜라이더가 붙은 Plane·Cube·Sphere·Capsule·Cylinder 등을 만든다. 빌드에서 쓰려면 MeshFilter·MeshRenderer·BoxCollider·SphereCollider 참조와 Default-Material이 있어야 하며, 없으면 분홍색으로 보인다. | https://docs.unity.com/en-us/engine/current/script-reference/unityengine/gameobject/createprimitive |
| 런타임 메시 생성 | 정점 배열과 삼각형 인덱스 배열(삼각형마다 정점 인덱스 3개)을 넣고 `RecalculateNormals`를 부른다. 정점을 매 프레임 바꾸려면 `SetVertices`로 다시 쓴다. 검사를 건너뛰는 고급 API(`SetVertexBufferData` 등)와 Job·Burst용 `MeshData`(`AllocateWritableMeshData`)도 있다. | https://docs.unity.com/en-us/engine/current/script-reference/unityengine/mesh |
| 인덱스 형식 | 16비트 인덱스는 메시당 정점 65,535개까지, 32비트는 약 40억 개까지다. 기본은 16비트다. 32비트 인덱스는 모든 GPU가 지원하지는 않는다(예: Mali-400 Android). | https://docs.unity.com/en-us/engine/current/script-reference/unityengine/mesh/indexformat |
| 파티클 | Built-in 파티클 시스템(Shuriken)은 이 프로젝트에 이미 있다(`docs/gen3d-feasibility.md` 2.4). VFX Graph는 URP·HDRP 전용이고 컴퓨트 셰이더가 필요하며 "isn't out of preview for mobile platforms"다. 이 프로젝트는 Built-in 렌더 파이프라인이므로 VFX Graph는 쓸 수 없다. | https://docs.unity3d.com/Packages/com.unity.visualeffectgraph@17.3/manual/System-Requirements.html |

이 저장소도 같은 구조다. `SceneLoader`·`ShapeModelFactory`가 `CreatePrimitive`로 구·정육면체·납작 원기둥을 만들고, `BaseShapeMesh`가 `form.base`(container·line·sheet·flame·drop)를 절차적으로 만든다. 선은 튜브(`tubeRadius`, `tubeSegments`), 천·종이는 처짐 판이고, 무작위성은 시드 고정 `SplitMix64`로 결정적이다(`unity/Assets/IFS/Runtime/Rendering/BaseShapeMesh.cs`). 해석기가 JSON의 닫힌 어휘를 받아 형상을 만드는 전형적인 구조다.

### 1.3 형상 자체를 데이터로 옮기는 표준: glTF 2.0

| 항목 | 확인한 내용 (Khronos 규격 원문) | 출처 |
| --- | --- | --- |
| 구조 | "glTF combines an easily parsable JSON scene description with one or more binary resources representing geometry, animations, and other rich data. These binary resources can often be loaded directly into GPU buffers with no additional parsing or processing." `.gltf` JSON 파일이 노드 계층·머티리얼·카메라와 메시·애니메이션의 기술자(descriptor)를 담고, 정점은 buffer → bufferView → accessor로 가리킨다. | https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html (2.3절, 2.2절) |
| 정점을 JSON에 넣을 때 | 버퍼를 JSON 안에 Data URI(base64)로 넣을 수 있지만, 규격은 이 방식이 "increases the overall size due to base64 encoding and does not support progressive or on-demand loading"이라고 적는다. 그래서 GLB 컨테이너(JSON 청크 + BIN 청크)를 권한다. | 같은 문서 (GLB 절) |
| 프리미티브 모드 | POINTS, LINES, LINE_LOOP, LINE_STRIP, TRIANGLES 등. | 같은 문서 (mesh.primitive.mode) |
| 재질 | 핵심 규격은 metallic-roughness PBR, `emissiveFactor`, `alphaMode`(OPAQUE: 알파 무시, MASK: 컷오프 기준 완전 불투명/완전 투명, BLEND)를 정의한다. 투과·부피·발광 세기는 확장(KHR_materials_*)으로 처리한다. | 같은 문서 (3.9절, 5.19절) |
| 애니메이션 | 핵심 규격의 애니메이션 대상은 노드의 translation·rotation·scale과 모프 타깃 weights다. | 같은 문서 (animation.channel.target.path) |
| glTFast의 지원 범위 (6.21, Built-in) | 지원: unlit, texture transform, alpha OPAQUE/MASK/BLEND, 정점 색, 모프 타깃, 스킨, legacy 애니메이션, POINTS·LINES 모드(점 구름은 Built-in에서 Unlit만). 미지원 또는 계획: `KHR_materials_emissive_strength`(행이 비어 있음), `KHR_animation_pointer`(행이 비어 있음), `KHR_materials_transmission`(계획, Built-in에서는 맑은 유리 같은 경우만 정확), `KHR_materials_volume`(Built-in은 지원 계획 없음). | https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@6.21/manual/features.html |

정리하면 glTF는 "JSON은 구조, 형상은 바이너리"로 나눈 표준이다. JSON 매개변수 스펙(IFSSceneSpec)과 glTF는 경쟁 관계가 아니다. 스펙은 무엇을 그릴지 정하고, glTF는 미리 만든 형상(에셋)을 싣는 그릇이다. 이 둘을 잇는 방식은 `docs/gen3d-feasibility.md` 2.4의 C안(검수 에셋 + 사전 선택)에 이미 정리되어 있다.

## 2. JSON·선언적 장면 기술을 중간 표현으로 쓴 연구

### 2.1 무엇을 확인했나

| 연구 (서지) | 엔진 | 중간 표현이 기술한 것 | 형상은 어디서 오나 | 보고된 한계 | 출처 |
| --- | --- | --- | --- | --- | --- |
| **WordsEye**. Coyne, Sproat. SIGGRAPH 2001, pp. 487–496 | 자체 렌더러 | 문장 → 의미 표현 → 묘사 규칙(depiction rules) → 저수준 **depictor**. depictor는 "3D object visibility, size, position, orientation, surface color and transparency", 자세, IK, 정점 변위를 지정한다. 기본값으로 넣은 depictor는 **tentative**로 표시하고, 명시된 depictor와 충돌하면 지운다. | 3D 모델·자세 DB. 추상 개념은 textualization(3D 글자), emblematization(전구 = 생각), conventional icons(생각 풍선), literalization, personification, degeneralization으로 그릴 수 있게 바꾼다. | 저자들이 직접 "infeasible to fully capture the semantic content of language in graphics"라고 적었다. 앞으로 필요한 것으로 "mechanisms for depicting materials and textures", "modifying geometric and surface properties of object parts (e.g. John has a long red nose)"를 든다. | https://www.cs.columbia.edu/~coyne/papers/wordseye_siggraph.pdf (PDF 본문 확인), https://history.siggraph.org/?p=116945 |
| **SceneSeer**. Chang, Eric, Savva, Manning. arXiv:1703.00050 (2017) | 웹 기반 | 자연어 → 장면 템플릿(물체·관계) → 3D 장면. 짧은 명령으로 반복 수정한다. | 3D 모델 DB 검색 | (요약만 확인) | https://arxiv.org/pdf/1703.00050 |
| **DXR**. Sicat, Li, Choi, Cordeil, Jeong, Bach, Pfister. IEEE TVCG 25(1), 2019 | **Unity** | Vega-Lite에서 따온 **JSON 사양**: data, mark, encoding(채널 ↔ 데이터 속성), 상호작용. 채널: x·y·z, width·height·depth·size, color·opacity, x/y/z rotation, x/y/z direction·length, offset. | 내장 마크 프리팹(cube, sphere, cone, text). **어떤 Unity 프리팹이든** 마크로 쓸 수 있고, 일반 마크 스크립트를 상속해 새 채널을 만든다. | 원문 미확인. 후속 Deimos(arXiv:2302.13655)는 마크가 많을 때 성능 때문에 오브젝트 풀링을 넣었다고 적는다(요약만 확인). | https://sites.google.com/view/dxr-vis/grammar-docs/mark, https://vcg.seas.harvard.edu/publications/20180820-dxr-a-toolkit-for-building-immersive-data-visualizations |
| **VRIA**. Butcher, John, Ritsos. IEEE TVCG 27(7):3213–3225, 2021 | WebVR, **A-Frame**, React, D3 | 선언적 **JSON 문법**(Vega-Lite·DxR과 비슷), JSON Schema(`vria-schema-v1.0.json`)를 공개했다. 빠진 값은 기본값으로 채운다. | A-Frame 프리미티브 | (요약만 확인) | https://github.com/vriajs/vria, https://research.bangor.ac.uk/en/publications/vria-a-web-based-framework-for-creating-immersive-analytics-exper/ |
| **IATK**. Cordeil 외. IEEE VR 2019 | **Unity** | JSON 문법이 아니라 GUI와 저수준 C# API로 만든다. 점을 개별 GameObject가 아니라 큰 메시 하나의 정점으로 넣고 셰이더로 그려 수백만 점을 다룬다고 밝힌다. | 셰이더 글리프 | 후속 연구(arXiv:2402.00344)는 코드 기반 맞춤 지원이 부족하다고 지적한다(요약만 확인). | https://research.monash.edu/en/publications/iatk-an-immersive-analytics-toolkit/ |
| **LLMR**. De La Torre, Fang, Huang, Banburski-Fahey, Amores Fernandez, Lanier. CHI 2024, DOI 10.1145/3613904.3642579 | **Unity** | JSON 장면 스펙이 **아니다**. 장면 계층을 JSON 문자열로 바꿔 Scene Analyzer에 넣고, Builder가 **C# 코드**를 생성해 Roslyn으로 런타임 컴파일한다. | Unity 프리미티브, Sketchfab 모델 검색(DALL·E 2 + CLIP 매칭) | 생성 코드가 "lacks robustness and frequently contains bugs". 한 요청에 1분 남짓 걸린다. Sketchfab 모델은 부품 이름이 무작위이고 방향·피벗 정보가 없어 회전이 어긋난다. | https://arxiv.org/html/2309.12276v3 |
| **DreamCodeVR**. Giunchi, Numan, Gatti, Steed. IEEE VR 2024 | **Unity** + Ubiq | 음성 → LLM → **C# 코드**(Roslyn)로 실행 중인 VR 앱의 외형·행동·상태를 바꾼다. | 기존 장면 물체 | (원문 미확인) | https://discovery.ucl.ac.uk/id/eprint/10190408 (요약만 확인) |
| **Holodeck**. Yang, Sun, Weihs, Clark 외. CVPR 2024 | AI2-THOR (**Unity** 렌더) | 층 평면은 파이프(\|) 구분 행, 물체 선택은 **JSON**, 배치는 "object \| global constraint \| constraint 1 …" 형태의 공간 관계 제약. 제약은 최적화로 풀어 좌표를 정한다. | Objaverse 등 51,464개 에셋 **검색**(생성 아님) | 복잡한 배치(식당 등)와 라이브러리에 없는 에셋(치과 X선 장비 등)에서 실패한다. LLM과 에셋 검색의 문화 편향. | https://arxiv.org/html/2312.09067v2 |
| **LayoutGPT**. Feng, Zhu 외. NeurIPS 2023 | — | **CSS(스타일시트) 형식** 배치를 LLM이 생성한다. 2D 이미지와 3D 실내 장면을 다룬다. | 3D 장면은 가구 경계 상자 + 기존 모델 | (요약만 확인) | https://proceedings.neurips.cc/paper_files/paper/2023/hash/3a7f9e485845dac27423375c934cb4db-Abstract-Conference.html |
| **SceneCraft**. Hu 외. ICML 2024 (PMLR 235) | Blender | 장면 그래프(공간 관계) → 수치 제약 → **Blender Python** 코드. 렌더 결과를 멀티모달 모델이 비평하고 고치는 루프. | 에셋 최대 약 100개 | (요약만 확인) | https://proceedings.mlr.press/v235/hu24g.html |
| **3D-GPT**. Sun, Han, Deng, Wang, Qin, Gould. arXiv:2310.12945 (v2 2024) | Blender + Infinigen | LLM이 Infinigen 절차적 생성 함수의 **매개변수**를 정하는 Python 코드를 쓴다. | 절차적 생성기(Infinigen)가 형상을 만든다 | (요약만 확인) | https://arxiv.org/html/2310.12945v2 |
| **VRCopilot**. Zhang, Pan, Gettig, Oney, Guo. UIST 2024, DOI 10.1145/3654777.3676451 | VR | 음성 + 직접 조작. 와이어프레임 같은 **중간 표현**을 둔 비계(scaffolded) 생성이 완전 자동 생성보다 사용자 주체감을 높였다. | 가구 데이터셋 | 원문의 JSON 사용 여부 미확인 | https://arxiv.org/abs/2408.09382v1 |

### 2.2 감정·통증을 형상으로 바깥에 내놓은 VR 연구

| 연구 (서지) | 무엇을 형상화했나 | 형상을 정하는 방식 | 이 연구와의 관계 | 출처 |
| --- | --- | --- | --- | --- |
| **MoodShaper**. Wagener, Kiesewetter, Reicherts, Woźniak, Schöning, Rogers, Niess. DIS 2024, DOI 10.1145/3643834.3661570 | 부정 감정 | **자유 3D 드로잉**(Open Brush 기반, 미리 만든 환경 9개, 애니메이션 포함 붓 12종, 색 패널). 개입 3종(종이비행기로 날려 보내기, 사진 찍어 유리구슬에 넣기, 빛 비추기) 동안 그림이 조금씩 사라진다. Quest 2 + AirLink. n=60. | 매개변수 스펙이 아니라 참여자가 직접 그린다. 말 → 스펙 → 형상 경로와 대비된다. | https://discovery.ucl.ac.uk/10194135/1/_DIS24__Mood_Shaper_Wagener.pdf (PDF 본문 확인) |
| **Letting It Go**. Wagener, Schöning, Rogers, Niess. IEEE VRW 2023, pp. 763–764 | 부정 감정 | 치료자 면담에서 나온 설계 개념 4개(Full Circle 등). 3D 물체로 바꾸는 구체 방식은 원문 미확인. | 설계 근거 | https://discovery.ucl.ac.uk/id/eprint/10172367 (요약만 확인) |
| **Pinilla 외**. Affective Visualization in Virtual Reality: An Integrative Review. Frontiers in Virtual Reality 2, 2021, DOI 10.3389/frvir.2021.630731 | 정서 상태 | 추상 도형(둥긂, 색의 밝기·채도, 질감, 움직임 속도·방향)을 생체 신호로 **자동 매개변수화**하자는 검토. | 형상 매개변수 ↔ 정서의 근거 문헌 모음. 색-감정 결과는 서로 엇갈린다는 후속 지적이 있다(요약만 확인). | https://public-pages-files-2025.frontiersin.org/journals/virtual-reality/articles/10.3389/frvir.2021.630731/text (초록만 확인) |
| **Bertheaux 외**. Effect of material properties on emotion: a virtual reality study. Front. Hum. Neurosci. 17:1301891, 2024 | 머그잔 재질 | Unity HDRP에서 금속성 4단계 × 매끄러움 4단계(16종), 색 제거. 두 속성 모두 valence·arousal에 유의한 양의 효과. | 재질 매개변수만 바꿔도 정서 평가가 달라진다는 근거 | https://pmc.ncbi.nlm.nih.gov/articles/PMC10847545/ |
| **Matamala-Gomez 외**. J. Clin. Med. 9(2):291, 2020 | 가상 팔 | 연구자가 팔의 모양(망원경식 왜곡)과 색을 조작. 왜곡이 통증 평가를 높였다. | 연구자 조작이며 참여자 표현이 아니다 | https://www.doi.org/10.3390/jcm9020291 (요약만 확인) |
| **Painimation**. Jonassaint 외, JMIR 2018 | 통증 질 | 태블릿의 **추상 애니메이션**을 고른다(VR 아님). 고른 애니메이션이 McGill 통증 질문지 형용사와 대응했다. | 닫힌 선택지에서 고르는 방식. 원칙 3(예시·선택지 금지)과 다르다. | https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6098242/ (요약만 확인) |

### 2.3 연구에서 읽히는 것

1. **JSON → 해석기 → 3D 구조는 확립된 방식이다.** DXR(Unity)과 VRIA(A-Frame)는 Vega-Lite식 선언 문법을 JSON으로 쓰고, 해석기가 프리팹이나 프리미티브에 채널을 입힌다. 이 저장소의 SceneSpec → Unity 로더와 구조가 같다.
2. **JSON으로 형상 자체를 기술한 사례는 드물다.** 대부분은 무엇을 어디에 둘지만 기술하고, 형상은 에셋 DB(WordsEye, SceneSeer, Holodeck, LLMR), 코드(LLMR, DreamCodeVR, SceneCraft), 절차적 생성기(3D-GPT/Infinigen)에서 온다. 형상을 기술하는 방식은 DXR처럼 크기·방향·색 채널을 프리팹에 입히는 정도다.
3. **LLM이 코드를 쓰는 방식은 결정성이 없다.** LLMR은 생성 코드의 버그와 1분 지연을 한계로 적었다. 이 저장소 원칙 1(장면 속성은 사전·규칙만)과 맞지 않는다.
4. **WordsEye의 tentative depictor는 이 저장소의 `defaultsUsed` 설계와 같은 생각이다.** 말하지 않은 값은 기본값으로 표시하고, 말한 값이 나오면 덮어쓴다. 추상 개념 처리 전략(emblem 등)은 말하지 않은 상징을 지어내는 일이라 이 저장소 원칙 2와 충돌한다.
5. **감정 외부화 VR은 자유 드로잉(MoodShaper)이나 연구자 조작(Matamala-Gomez)이 주류다.** "참여자의 말 → 화이트박스 규칙 → 매개변수 형상" 경로를 쓴 VR 연구는 이번 검색 범위에서는 찾지 못했다. 새로움 주장의 근거로 쓰려면 ACM DL에서 더 체계적으로 찾아야 한다.

## 3. JSON 매개변수 방식으로 형상을 표현할 때의 한계

### 3.1 닫힌 어휘

JSON 스펙은 해석기가 아는 키와 값만 그릴 수 있다. DXR의 채널 목록, VRIA의 스키마, 이 저장소의 enum(`form.type` 4개, `form.base` 5개, `baseVariant` 하위 값들)이 모두 그렇다. 새 형상을 넣으려면 스키마, 사전, 해석기, 테스트를 함께 바꿔야 한다. 이것은 단점이면서 장점이다. 같은 입력이 같은 결과를 내고(원칙 1), 무엇을 못 그렸는지 `_unmapped`로 기록할 수 있다. WordsEye도 이 문제를 "infeasible to fully capture the semantic content of language in graphics"로 인정했다.

### 3.2 임의 지오메트리

JSON에 정점과 삼각형 배열을 숫자로 나열하는 것은 기술적으로 가능하다. Unity `Mesh`가 받는 입력이 바로 그것이다. 하지만 다음 이유로 실용적이지 않다.

- **크기와 속도.** glTF 규격은 바이너리를 JSON에 base64로 넣는 방식이 크기를 늘리고 점진 로딩을 막는다고 적고, 그래서 GLB를 권한다(1.3절). 숫자를 문자열로 쓰는 일반 JSON은 더 크고 파싱도 느리다.
- **인덱스 상한.** 16비트 인덱스는 메시당 정점 65,535개까지다. 32비트는 일부 모바일 GPU에서 지원되지 않는다(1.2절).
- **저작 문제.** 정점 목록은 사람이 쓰거나 규칙이 만들 수 있는 표현이 아니다. 말에서 정점 좌표로 가는 화이트박스 규칙은 없다. 정점 목록이 필요하면 누군가(모델러나 생성 모델)가 미리 만든 것이어야 하고, 그 순간 말하지 않은 세부가 들어간다(`docs/gen3d-feasibility.md` 7절의 생성형 문제).

따라서 형상을 JSON에 넣는 현실적인 방법은 **매개변수 몇 개로 형상군 전체를 덮는 표현**이다.

### 3.3 연속 형상 공간을 주는 매개변수 표현

| 표현 | 1차 출처 | 매개변수 | 덮는 형상 | 못 하는 것 | Unity·Quest 구현 |
| --- | --- | --- | --- | --- | --- |
| **슈퍼쿼드릭(초타원체)** | Barr, IEEE CG&A 1(1):11–23, 1981, DOI 10.1109/MCG.1981.1673799. "complex solids and surfaces can be constructed and altered easily from a few interactive parameters" | 축별 크기 3개 + 모양 지수 2개(ε1, ε2). 초원환체(supertoroid)는 구멍 반지름 1개 추가 | 구, 정육면체에 가까운 둥근 상자, 원판, 원기둥, 팔면체형, 별처럼 오목한 형태, 길쭉·납작. Paschalidou 외(CVPR 2019)는 슈퍼쿼드릭 조합이 직육면체 조합보다 형상을 더 잘 나타낸다고 보고했다. | 국소 돌기, 비대칭, 구멍(초원환체 제외) | 구면 매개변수화로 메시 생성. C# 수백 줄. 로드 때 한 번 만들면 Quest 비용은 일반 메시와 같다. |
| **슈퍼포뮬러** | Gielis, Am. J. Bot. 90(3):333–338, 2003, DOI 10.3732/ajb.90.3.333 | 2D 곡선당 m, n1, n2, n3, a, b. 두 곡선의 구면 곱으로 3D | 꽃잎·별·톱니·다각형 대칭 형태. 슈퍼쿼드릭을 포함한다. | 매개변수와 형상 인상이 직관적으로 대응하지 않는다(사전 단계 설계가 어렵다) | 슈퍼쿼드릭과 같은 메시 생성 경로 |
| **메타볼(blobby)** | Blinn, ACM TOG 1(3):235–256, 1982 | 공 중심·반지름·세기 N개 | 덩어리 여러 개가 녹아 붙은 형태, 돌기, 혹 | 날카로운 모서리 | 음함수 → 메시는 마칭 큐브(Lorensen, Cline, SIGGRAPH 1987)로 로드 때 굽는다. 실시간 변형은 Quest에서 비용이 크다(추론, 미측정). |
| **SDF·CSG** | Hart, The Visual Computer 12(10):527–545, 1996 (sphere tracing) | 프리미티브 SDF + 합·차·교·부드러운 합 연산 트리 | 구멍, 속 빈 껍질, 파임, 깎임, 조합 형태. 위상 변화(구멍)를 표현할 수 있는 유일한 후보군이다. | 트리가 깊어지면 사람이 읽기 어렵다 | 두 길: (a) 로드 때 마칭 큐브로 메시화(기존 렌더 경로 유지), (b) 픽셀 셰이더 레이마칭. (b)는 화면 픽셀마다 반복 계산이라 Quest 단독 실행에서 위험하다(추론, 미측정). |
| **L-시스템** | Prusinkiewicz, Lindenmayer, *The Algorithmic Beauty of Plants*, Springer 1990 (https://algorithmicbotany.org/papers/abop/abop.pdf) | 공리, 재작성 규칙, 반복 횟수, 각도 | 가지, 뿌리, 갈라짐, 실타래 같은 재귀 구조 | 덩어리 형상 | 문자열 → 튜브 메시. 이미 있는 line 튜브 생성기를 재사용할 수 있다. |
| **노이즈 변위** | (표준 기법. 이 저장소 형태 셰이더가 이미 씀, `unity/README.md`) | 진폭, 주파수, 시드 | 울퉁불퉁, 거칢, 침식된 가장자리 | 큰 형상 변화 | 정점 셰이더나 로드 때 메시 변형. 이미 있다. |
| **파티클** | Unity Built-in Particle System (VFX Graph는 Built-in 미지원, 1.2절) | 방출량, 수명, 속도, 크기, 색 곡선, 모양(구·원뿔·메시 표면) | 먼지, 안개, 빛 알갱이, 흩어짐, 연기 | 단단한 형상 | 반투명 입자는 겹쳐 그리기(overdraw) 비용이 크다. Meta 성능 문서에서 Quest용 수치는 찾지 못했다(확인 필요). |

### 3.4 질감·움직임·반투명·발광의 표현 범위

| 속성 | glTF 핵심 규격 | glTFast(Built-in) | Unity Built-in에서 직접 | 이 저장소 SceneSpec 현재 |
| --- | --- | --- | --- | --- |
| 색 | baseColorFactor, 정점 색 | 지원 | 머티리얼 색 | `material.color`, `brightness`, `saturation` |
| 거칠기·금속성 | metallic-roughness | 지원 | Standard 셰이더 | `material.roughness`. 금속성 슬롯은 없다 |
| 질감 패턴 | 텍스처 + `KHR_texture_transform` | 지원 | 텍스처·절차 셰이더 | 슬롯 없음 |
| 반투명 | alphaMode MASK/BLEND | 지원 | 투명 큐, 정렬 문제 있음 | `material.opacity` |
| 투과·굴절 | 확장(transmission, volume) | 부분 지원 / 지원 계획 없음 | 별도 셰이더 필요 | 없음 |
| 발광 | emissiveFactor (세기 확장은 별도) | emissive는 지원, `emissive_strength` 미지원 | Standard 셰이더 Emission | 슬롯 없음 |
| 움직임 | 노드 TRS·모프 weights 애니메이션 | legacy 지원, Mecanim 부분 | 스크립트, Animator | `motion.type` 20개 + `motion.speed`. 스크립트가 그린다(`SpecMotion.cs`) |
| 형태가 시간에 따라 바뀜 | 모프 타깃 | 지원 | 블렌드셰이프·정점 재계산 | 없음(로드 때 한 번 정함, `docs/shape-mapping.md` 한계) |
| 입자·부피 | 핵심 규격에 없음 | — | Shuriken | mist 덩어리(`MistLumps.cs`) |

출처: glTF 규격(https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html), glTFast 기능 표(https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@6.21/manual/features.html).

### 3.5 Quest 단독 실행 제약

| 항목 | 확인한 수치 | 출처 |
| --- | --- | --- |
| 그리기 호출 | Quest 3/3S: 가벼운 장면 700–1,000, 중간 400–600. Quest 2/Pro: 가벼운 장면 400–600. 메시 공유·인스턴싱을 권한다. | https://developers.meta.com/horizon/documentation/unity/unity-perf/ |
| 삼각형 | Quest 2/Pro 75만–100만, Quest 3/3S 130만–180만(프레임당, 내부 권장 범위) | 같은 문서 |
| 반투명·겹쳐 그리기 | 같은 문서는 Unity의 overdraw 보기 모드만 언급하고 수치 지침은 없다 | 같은 문서 |
| VFX Graph | URP·HDRP 전용, 모바일은 preview. Built-in인 이 프로젝트에서는 못 쓴다. | https://docs.unity3d.com/Packages/com.unity.visualeffectgraph@17.3/manual/System-Requirements.html |

이 저장소의 장면은 물체 하나와 환경 정도라 그리기 호출과 삼각형 예산에는 여유가 크다(추론). Quest에서 실제로 위험한 것은 (a) 픽셀 셰이더 레이마칭(SDF를 실시간으로 그릴 때), (b) 반투명 입자가 화면을 크게 덮는 경우, (c) 매 프레임 메시 재계산이다. 셋 다 기기 측정이 필요하다.

## 4. 이 저장소 IFSSceneSpec에 주는 시사점

### 4.1 현재 스펙이 표현하지 못하는 형상

스키마 v2.2와 `docs/shape-mapping.md`로 보면, 현재 형상 표현은 `form.type`(blob, mist, shell, fragments), `form.base`(container, line, sheet, flame, drop)와 변형(opening, profile, form, gauge, drape), 자세(`form.posture` 16개, 크기 배율로 구현), 모양어 모형(구·정육면체·납작 원기둥 등)이다. 이 틀 밖에 있는 것은 다음과 같다.

| 못 그리는 것 | 예 (사전에 이미 있는 모양 값) | 원인 |
| --- | --- | --- |
| 모양의 **정도**(연속값) | 둥근 정도, 각진 정도, 길쭉함·납작함의 비율 | 모양 값이 범주(enum)이고 정도 축이 없다 |
| **부분** 형상 | 「끝이 뾰족해요」(전체가 원뿔이 됨), 가장자리(`edge`) | 부분 슬롯이 없다(`docs/shape-mapping.md` 한계 1) |
| **위상** | 구멍(`hole`), 속 빔(`hollow`), 고리 | 메시 생성기에 구멍 있는 형태가 없다 |
| 표면 **요철** | 울퉁불퉁(`bumpy`), 날카로움(`sharp`) | 노이즈는 있지만 사전 값과 연결된 매개변수가 아니다 |
| **점·입자** 형상 | 점(`dot`), 흩어진 알갱이, 빛 알갱이 | `fragments`는 파편 메시이고 입자 슬롯이 없다 |
| **발광** | 「주황색 빛 덩어리」 | `material`에 emission 슬롯이 없다 |
| 시간에 따른 **형태 변화** | 부풀었다 줄어듦, 녹아내림 | 형태는 로드 때 한 번 정하고, motion은 위치·회전만 바꾼다 |
| 여러 덩어리 사이의 **관계** | 덩어리 둘이 붙어 있음, 하나가 다른 것을 감쌈 | 스펙이 물체 하나를 기술한다 |
| 알아볼 수 있는 구체 사물 | 손, 병, 벽 | 에셋 경로(`docs/gen3d-feasibility.md` C안) 몫이고 이 문서 범위 밖이다 |

### 4.2 확장 후보

모든 후보는 원칙 1·2를 지킨다. 값은 사전 낱말에서만 오고, 정도는 연속 실수가 아니라 서수 단계(예: 조금·보통·많이)로 둔다. 말하지 않은 매개변수는 기본값으로 그리되 `defaultsUsed`에 남긴다(WordsEye의 tentative depictor와 같은 처리). 같은 스펙은 시드 고정으로 같은 메시를 낸다.

| # | 후보 | 스펙 변경 (예시 키) | 새로 그릴 수 있는 것 | 구현 비용 어림 | 위험 |
| --- | --- | --- | --- | --- | --- |
| E1 | **슈퍼쿼드릭 윤곽** | `form.profile = {roundness: sharp\|soft\|round, aspect: tall\|flat\|even}` 같은 서수 값 → 해석기가 ε1·ε2와 축 비율로 바꿈 | 각짐↔둥긂의 정도, 길쭉·납작·원판, 「모난」「동글동글한」 | 낮음~중간. 메시 생성기 C# 약 200–300줄, 서수 → 지수 표, EditMode 테스트, 사전 낱말 연결. 기존 모양어 모형(구·정육면체·원판)을 이것으로 대체할 수 있다. | 낮음. 로드 때 한 번 만드는 메시라 Quest 비용이 거의 없다. |
| E2 | **부분 슬롯** | `_parts`(이미 v1 기록 있음)를 렌더 입력으로 승격: `form.parts = [{part: tip\|edge\|surface, shape: sharp\|bumpy\|round}]` | 「끝이 뾰족」「가장자리가 울퉁불퉁」을 전체가 아니라 부분에만 적용 | 중간. 정점 마스크(축 방향 끝, 가장자리) + 국소 변위. 추출기에서 부분-모양어 짝을 찾는 규칙과 테스트가 필요하다. | 중간. 부분 판정 규칙이 틀리면 엉뚱한 곳이 변한다. |
| E3 | **입자 형태** | `form.type`에 `particles` 추가 또는 `form.particles = {density, grain: dot\|dust\|spark}` | 점, 흩어짐, 먼지, 빛 알갱이. mist가 거의 안 보이는 문제의 대안 | 낮음~중간. Shuriken 설정 프리셋 + 결정적 시드(`randomSeed` 고정, `useAutoRandomSeed = false`). | 중간. 반투명 입자 overdraw는 Quest 실측이 필요하다. VFX Graph는 못 쓴다. |
| E4 | **발광** | `material.emission = none\|dim\|bright` (색은 `material.color` 재사용) | 「빛 덩어리」「환하게 빛나는」 | 낮음. Built-in Standard 셰이더의 Emission(또는 IFS 셰이더에 항 하나 추가), 사전 낱말 몇 개. | 낮음. 블룸 후처리를 넣으면 비용이 생기므로 넣지 않는 쪽을 권한다. |
| E5 | **구멍·속 빔(위상)** | `form.topology = solid\|hollow\|holed` | 구멍, 고리, 속 빈 껍질 | 높음. SDF + CSG를 로드 때 마칭 큐브로 굽는 경로가 일반적이다. 더 싸게 가려면 초원환체(E1 확장) 하나와 `shell` 두께 조절로 일부만 덮는다. | 중간. 실시간 레이마칭은 Quest에서 피한다. |

추천 순서는 E1 → E4 → E3 → E2 → E5다. E1과 E4는 비용이 낮고, `docs/shape-mapping.md`「아직 모형이 없는 모양 값」(angular, elongated, thick, thin, circle 등)과 합성 예문의 빛 심상을 바로 덮는다. E2는 이미 문서화된 한계(부분 모양어가 전체에 적용됨)를 고친다. E5는 비용 대비 덮는 낱말(hole, hollow)이 적다. 시간에 따른 형태 변화와 여러 덩어리 관계는 스펙 구조(물체 하나, 정적 형태)를 바꿔야 하므로 이번 후보에 넣지 않았다.

## 5. 참고문헌

Unity·표준 문서
- Unity. JSON serialization (JsonUtility). https://docs.unity.com/en-us/engine/current/manual/programming-environment/code-reload-serialization/script-serialization/json-serialization
- Unity. Serialization rules. https://docs.unity.com/en-us/engine/current/manual/programming-environment/code-reload-serialization/script-serialization/rules
- Unity. Mesh (Script Reference). https://docs.unity.com/en-us/engine/current/script-reference/unityengine/mesh
- Unity. Mesh.indexFormat. https://docs.unity.com/en-us/engine/current/script-reference/unityengine/mesh/indexformat
- Unity. GameObject.CreatePrimitive. https://docs.unity.com/en-us/engine/current/script-reference/unityengine/gameobject/createprimitive
- Unity. Newtonsoft Json package 3.2. https://docs.unity3d.com/Packages/com.unity.nuget.newtonsoft-json@3.2/manual/index.html
- Unity. Visual Effect Graph 17.3 System Requirements. https://docs.unity3d.com/Packages/com.unity.visualeffectgraph@17.3/manual/System-Requirements.html
- Unity. glTFast 6.21 Features. https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@6.21/manual/features.html
- Khronos Group. glTF 2.0 Specification. https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html
- Meta. Unity performance (Draw calls / Triangles on Meta Quest). https://developers.meta.com/horizon/documentation/unity/unity-perf/

장면 생성·시각화 문법
- Coyne, B., Sproat, R. (2001). WordsEye: An Automatic Text-to-Scene Conversion System. SIGGRAPH 2001, 487–496. https://www.cs.columbia.edu/~coyne/papers/wordseye_siggraph.pdf
- Chang, A. X., Eric, M., Savva, M., Manning, C. D. (2017). SceneSeer: 3D Scene Design with Natural Language. arXiv:1703.00050. https://arxiv.org/pdf/1703.00050
- Sicat, R., Li, J., Choi, J., Cordeil, M., Jeong, W.-K., Bach, B., Pfister, H. (2019). DXR: A Toolkit for Building Immersive Data Visualizations. IEEE TVCG 25(1). https://vcg.seas.harvard.edu/publications/20180820-dxr-a-toolkit-for-building-immersive-data-visualizations
- Butcher, P., John, N. W., Ritsos, P. D. (2021). VRIA: A Web-Based Framework for Creating Immersive Analytics Experiences. IEEE TVCG 27(7), 3213–3225. https://ieeexplore.ieee.org/document/8954824
- Cordeil, M. 외 (2019). IATK: An Immersive Analytics Toolkit. IEEE VR 2019. https://research.monash.edu/en/publications/iatk-an-immersive-analytics-toolkit/
- De La Torre, F., Fang, C. M., Huang, H., Banburski-Fahey, A., Amores Fernandez, J., Lanier, J. (2024). LLMR: Real-time Prompting of Interactive Worlds using Large Language Models. CHI 2024. DOI 10.1145/3613904.3642579. https://arxiv.org/html/2309.12276v3
- Giunchi, D., Numan, N., Gatti, E., Steed, A. (2024). DreamCodeVR: Towards Democratizing Behavior Design in Virtual Reality with Speech-Driven Programming. IEEE VR 2024. https://discovery.ucl.ac.uk/id/eprint/10190408
- Yang, Y., Sun, F.-Y., Weihs, L., Clark, C. 외 (2024). Holodeck: Language Guided Generation of 3D Embodied AI Environments. CVPR 2024. https://arxiv.org/html/2312.09067v2
- Feng, W., Zhu, W. 외 (2023). LayoutGPT: Compositional Visual Planning and Generation with Large Language Models. NeurIPS 2023. https://proceedings.neurips.cc/paper_files/paper/2023/hash/3a7f9e485845dac27423375c934cb4db-Abstract-Conference.html
- Hu, Z. 외 (2024). SceneCraft: An LLM Agent for Synthesizing 3D Scenes as Blender Code. ICML 2024, PMLR 235. https://proceedings.mlr.press/v235/hu24g.html
- Sun, C., Han, J., Deng, W., Wang, X., Qin, Z., Gould, S. (2023/2024). 3D-GPT: Procedural 3D Modeling with Large Language Models. arXiv:2310.12945. https://arxiv.org/html/2310.12945v2
- Zhang, L., Pan, J., Gettig, J., Oney, S., Guo, A. (2024). VRCopilot: Authoring 3D Layouts with Generative AI Models in VR. UIST 2024. DOI 10.1145/3654777.3676451. https://arxiv.org/abs/2408.09382v1

감정·통증 VR
- Wagener, N., Kiesewetter, A., Reicherts, L., Woźniak, P. W., Schöning, J., Rogers, Y., Niess, J. (2024). MoodShaper: A Virtual Reality Experience to Support Managing Negative Emotions. DIS 2024. DOI 10.1145/3643834.3661570. https://discovery.ucl.ac.uk/10194135/1/_DIS24__Mood_Shaper_Wagener.pdf
- Wagener, N., Schöning, J., Rogers, Y., Niess, J. (2023). Letting It Go: Four Design Concepts to Support Emotion Regulation in Virtual Reality. IEEE VRW 2023, 763–764. https://discovery.ucl.ac.uk/id/eprint/10172367
- Pinilla, A., Garcia, J., Raffe, W., Voigt-Antons, J.-N., Spang, R. P., Möller, S. (2021). Affective Visualization in Virtual Reality: An Integrative Review. Frontiers in Virtual Reality 2. DOI 10.3389/frvir.2021.630731
- Bertheaux, C., Zimmermann, E., Gazel, M., Delanoy, J., Raimbaud, P., Lavoué, G. (2024). Effect of material properties on emotion: a virtual reality study. Front. Hum. Neurosci. 17, 1301891. https://pmc.ncbi.nlm.nih.gov/articles/PMC10847545/
- Matamala-Gomez, M. 외 (2020). Manipulating the Perceived Shape and Color of a Virtual Limb Can Modulate Pain Responses. J. Clin. Med. 9(2), 291. https://www.doi.org/10.3390/jcm9020291
- Jonassaint, C. R. 외 (2018). Abstract Animations for the Communication and Assessment of Pain in Adults: Cross-Sectional Feasibility Study. JMIR. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6098242/

매개변수 형상
- Barr, A. H. (1981). Superquadrics and Angle-Preserving Transformations. IEEE CG&A 1(1), 11–23. DOI 10.1109/MCG.1981.1673799. https://authors.library.caltech.edu/9756
- Gielis, J. (2003). A generic geometric transformation that unifies a wide range of natural and abstract shapes. American Journal of Botany 90(3), 333–338. DOI 10.3732/ajb.90.3.333
- Blinn, J. F. (1982). A Generalization of Algebraic Surface Drawing. ACM TOG 1(3), 235–256. https://www.cs.jhu.edu/~misha/Fall25/Readings/Blinn82.pdf
- Hart, J. C. (1996). Sphere Tracing: A Geometric Method for the Antialiased Ray Tracing of Implicit Surfaces. The Visual Computer 12(10), 527–545. DOI 10.1007/s003710050084
- Lorensen, W. E., Cline, H. E. (1987). Marching Cubes: A High Resolution 3D Surface Construction Algorithm. SIGGRAPH '87, Computer Graphics 21(4), 163–169. https://history.siggraph.org/?p=116072
- Prusinkiewicz, P., Lindenmayer, A. (1990). The Algorithmic Beauty of Plants. Springer. https://algorithmicbotany.org/papers/abop/abop.pdf
- Paschalidou, D., Ulusoy, A. O., Geiger, A. (2019). Superquadrics Revisited: Learning 3D Shape Parsing beyond Cuboids. CVPR 2019, 10344–10353. https://arxiv.org/abs/1904.09970v1

## 6. 확인 필요

원문을 열지 못했거나 출처끼리 어긋나는 것이다. 논문에 인용하기 전에 원문으로 확인한다.

1. **DXR**: TVCG 25(1) 게재는 확인했다. IEEE VIS 2018 발표 여부와 논문 본문의 성능 한계는 원문을 열지 못했다(Edinburgh PDF가 10 MB를 넘어 실패).
2. **VRIA, IATK, SceneSeer, LayoutGPT, SceneCraft, 3D-GPT, DreamCodeVR**: 검색 결과 요약과 초록만 확인했다. 3D-GPT의 학회 게재 여부(3DV 등)는 확인하지 못했고 arXiv만 확인했다. SceneSeer는 arXiv 기술 보고서 외 게재처를 확인하지 못했다.
3. **VRCopilot**의 중간 표현이 JSON인지 확인하지 못했다.
4. **Letting It Go**에서 감정을 3D 물체로 바꾸는 구체 방식은 확인하지 못했다.
5. **Pinilla 외 2021**: 초록만 확인했다. 권하는 형상·색·움직임 매개변수의 구체 내용과 "색-감정 결과가 엇갈린다"는 지적(2026 arXiv 후속 연구, 검색 요약)은 원문 확인이 필요하다.
6. **Matamala-Gomez 2020, Painimation(Jonassaint 2018)**: 검색 요약만 봤다. Matamala-Gomez는 참여자 수가 출처마다 27명과 30명으로 다르다.
7. **Blinn 1982 DOI**(10.1145/965145.801290과 10.1145/357306.357310이 다름)와 **Lorensen·Cline 1987 DOI**(37401.37422와 37402.37422가 다름)는 ACM DL에서 확인해야 한다.
8. **Newtonsoft 패키지**의 Unity 6 최신 버전은 확인하지 않았다(3.2 문서만).
9. **Quest 반투명·입자 비용**: Meta 성능 문서에 수치 지침이 없었다. 레이마칭 SDF와 반투명 입자의 Quest 비용은 이 문서에서 추론으로만 적었고, 기기 측정이 필요하다.
10. **"말 → 규칙 → 매개변수 형상" VR 선행 연구가 없다는 판단**은 이번 웹 검색 범위 안에서의 결과다. 새로움 주장에 쓰려면 ACM DL·IEEE Xplore에서 체계적으로 찾아야 한다.
