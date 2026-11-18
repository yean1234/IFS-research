# CP5 — 같은 말·다른 값 구현 검토 (Codex)

- 일시: 2026-11-18
- 호출: `codex exec --sandbox read-only -c model_reasoning_effort="medium"` (RQ v2 작업 2/3회)
- 프롬프트: `docs/codex-reviews/prompts/CP5_prompt.md`
- 검토 대상: 커밋 `f5b4e69..562bd72`의 `unity/`, `chatbot/`, `shared/` 변경
- 판정(수용/반박/보류)은 `docs/decisions.md`에 적습니다.

---

### 높음

- **높음 [2·7] → ‘내 것’ 평정이 Q1의 ‘닮았다’ 효과로 집계된다.**  
  재현: 0.3에서 `ratingItem=mine`, `p=.5`, `w=.3`, `lo=.2`, `hi=.4`, 평정 `lo=2`, `hi=7`이면 `nearMinusFar.primary`에 `+5`가 들어간다. 0.2의 ‘내 것’과 0.3의 ‘닮았다’도 기존 RQ 집계에서 평균된다. 같은 참여자·세션으로 두 문항을 별도 실행하면 최근 완료본만 남는다.  
  근거: [OwnershipManifest.cs:63](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipManifest.cs:63), [ownership.py:184](<repo>/chatbot/ifs_chatbot/eval/ownership.py:184), [ownership.py:520](<repo>/chatbot/ifs_chatbot/eval/ownership.py:520), [ownership.py:580](<repo>/chatbot/ifs_chatbot/eval/ownership.py:580).  
  수정: 0.2의 문항을 `mine`으로 명시하고, 문항과 블록을 기록 선택 및 집계 키에 넣고, Q1은 `resemblance`만 받는다.

- **높음 [1·2·6] → 같은 물리 크기를 두 척도가 다르게 부호화해 가까운 쪽이 뒤집힌다.**  
  재현: 수치 크기 매핑에서 약 8.7cm는 `w=.30`이고 쌍은 `.20/.40`이다. 12cm를 보고하면 웹은 `p≈.114`를 기록해 `size_lo`를 가까운 쪽으로 가른다. 수치 크기 매핑으로 같은 12cm는 `p≈.377`이어서 `size_hi`가 가까운 쪽이다. 양쪽 평정이 2와 7이면 대비 부호도 바뀐다. Unity의 실제 폭에는 자세 변형도 곱해진다.  
  근거: [scene_builder_v1.py:408](<repo>/chatbot/ifs_chatbot/scene_builder_v1.py:408), [scene_params.v1.json:110](<repo>/shared/lexicon/scene_params.v1.json:110), [prereport.js:106](<repo>/chatbot/ifs_chatbot/web/prereport.js:106), [SceneLoader.cs:714](<repo>/unity/Assets/IFS/Runtime/Loading/SceneLoader.cs:714), [ownership_shift.py:137](<repo>/chatbot/ifs_chatbot/eval/ownership_shift.py:137).  
  수정: 수치 발화·보고·자극이 비교할 물리 치수를 하나로 정하고, 보고 원단위와 Unity 실측 폭을 기록해 같은 단위에서 비교한다.

- **높음 [6] → 형상을 본 뒤 제출한 보고가 ‘보기 전’ 주 분석에 들어간다.**  
  재현: 면담 확정 → Unity 실행·평정 완료 → 웹 보고 제출 → 분석 순서가 통과한다. 제출은 확정 텍스트와 파일 유무만 보며, 분석은 보고 시각과 최초 제시 시각을 대조하지 않는다.  
  근거: [controller.py:420](<repo>/chatbot/ifs_chatbot/controller.py:420), [OwnershipRunner.cs:305](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipRunner.cs:305), [OwnershipRunner.cs:430](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipRunner.cs:430), [ownership.py:522](<repo>/chatbot/ifs_chatbot/eval/ownership.py:522).  
  수정: 주 분석용 실행은 보고 접수 뒤에 열고, 분석에서도 접수와 최초 제시의 순서를 검증한다.

- **높음 [6·7] → 보고 연결 검사가 실패해도 다른 보고를 채택할 수 있다.**  
  재현: manifest 해시가 `"0"`이고 다른 세션의 보고를 넣으면 경고 뒤 그대로 라벨을 붙인다. 해시가 일치해도 세션 ID 불일치는 경고뿐이다. 제출 직전에 장면 파일을 교체하면 서버는 교체본 해시를 붙이며, 대체 매핑 파일도 현재 확정 때 생성된 목록 대신 파일 존재로 고른다.  
  근거: [ownership_shift.py:107](<repo>/chatbot/ifs_chatbot/eval/ownership_shift.py:107), [controller.py:444](<repo>/chatbot/ifs_chatbot/controller.py:444), [prereport.py:53](<repo>/chatbot/ifs_chatbot/prereport.py:53), [controller.py:869](<repo>/chatbot/ifs_chatbot/controller.py:869).  
  수정: 확정 시 생성한 파일별 해시를 고정하고, 세션 ID와 유효한 해시가 모두 일치할 때만 보고를 연결한다.

### 중간

- **중간 [1] → 엄격한 거리 부등식이 소수 경계에서 등호를 통과시킨다.**  
  재현: `w=.5, lo=.4, hi=.6, p=.55`는 `d(hi,p)=d(w,p)=.05`지만 `size_hi`가 채택된다. 실제 색 쌍 `.6000/.5556/.6556`에서 `p=.6278`도 같은 오류로 `color_hi`가 채택된다. `p=.1278`은 원형에서 `d(w,p)=d(hi,p)=.4722`인데 `color_lo`가 채택된다. 같은 쌍에서 정확한 반대편 `p=.1000`은 `beyond_far`로 정상 제외된다. 비대칭 이동에서 `p=.626`이 문턱을 넘고도 `order_violation`인 것도 정상이다.  
  근거: [ownership_shift.py:69](<repo>/chatbot/ifs_chatbot/eval/ownership_shift.py:69), [ownership_shift.py:206](<repo>/chatbot/ifs_chatbot/eval/ownership_shift.py:206), [manifest_stated.json:603](<repo>/chatbot/tests/fixtures/ownership_v03/manifest_stated.json:603).  
  수정: 기록 정밀도에 맞춘 고정소수점에서 원형 거리와 반 이동폭을 계산하고, 세 거리의 등호를 일관되게 제외한다.

- **중간 [2·3] → 분석기가 실제 제시 목록 밖의 평정으로 쌍을 완성한다.**  
  재현: `shiftPairs.size.valid=true`인 기록에서 `size_hi`를 `order`와 `variants`에서 빼고 CSV 행을 남기면 경고와 함께 대비가 집계된다. 0.3 CSV의 `item`이 빈 행도 통과해 앞선 정상 평정을 덮을 수 있다. 정상 생성 경로는 두 변형을 함께 추가하고 로드 실패 시 시작을 거부한다.  
  근거: [OwnershipVariantGenerator.cs:327](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipVariantGenerator.cs:327), [OwnershipRunner.cs:332](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipRunner.cs:332), [OwnershipRecordWriter.cs:162](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipRecordWriter.cs:162), [ownership.py:376](<repo>/chatbot/ifs_chatbot/eval/ownership.py:376), [ownership.py:527](<repo>/chatbot/ifs_chatbot/eval/ownership.py:527).  
  수정: 0.3은 비어 있지 않은 일치 문항과 두 `kind=shift` 변형의 제시 위치·평정을 검증한 뒤 쌍을 채택한다.

- **중간 [1·3·5] → `stated`가 실제 값의 출처보다 근거 배열의 존재를 따른다.**  
  재현: `layout.size=null`인데 `_provenance["layout.size"]`가 남아 있는 파일은 Unity에서 형식 경고로 진행된다. 기본값 `.5`가 `basis=stated`가 되어 주 분석에 들어간다. 반대로 색 값에 근거가 있고 명시 채도에 근거가 빠진 파일은 `mixed`가 되어 보고한 색상 축까지 제외된다.  
  근거: [OwnershipRunner.cs:278](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipRunner.cs:278), [SceneParams.cs:65](<repo>/unity/Assets/IFS/Runtime/SceneSpec/SceneParams.cs:65), [OwnershipVariantGenerator.cs:389](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipVariantGenerator.cs:389), [OwnershipVariantGenerator.cs:650](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipVariantGenerator.cs:650), [ownership_shift.py:198](<repo>/chatbot/ifs_chatbot/eval/ownership_shift.py:198).  
  수정: 값과 근거가 일치하는지 검사하고, 축 값의 출처와 축 선택에 관여한 채도의 출처를 따로 기록한다.

- **중간 [3] → 크기 판정이 `.5`에서 불연속이고 실제 원본을 기준으로 대칭을 확인하지 않는다.**  
  재현: 근거 있는 `w=.4999`는 범주 이탈로 제외되지만 `.49996`은 `.5`로 반올림돼 `.4/.6`이 통과한다. 정확히 `.5`인 경우에도 낱말·수치 근거와 무관하게 범주 검사가 빠진다. `sizeShiftStep=.00001`은 설정 검사를 통과하고 양끝이 원본과 같아져 세션 시작 오류를 낸다.  
  근거: [OwnershipConfig.cs:93](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipConfig.cs:93), [OwnershipVariantGenerator.cs:375](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipVariantGenerator.cs:375), [OwnershipVariantGenerator.cs:682](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipVariantGenerator.cs:682).  
  수정: 원본 해석값과 크기 근거의 범주를 사용하고, 실제 적용할 양끝의 범위·서로 다른 값·대칭을 함께 검증한다.

- **중간 [3] → 색 검색이 가능한 대칭 쌍을 놓치고, 양자화 뒤 색상각 상한도 넘는다.**  
  재현: `h=.6, s=.5, l=.4`, 밝기 `.5`, 상한 `21°`, 대칭 허용 `.1`이면 첫 목표 도달점 `−16°/+20°`의 ΔE는 `12.504/12.064`라 제외된다. `−16°/+21°`는 `12.504/12.580`으로 통과할 수 있다. 기본 상한에서도 기록된 `.6556`은 `.6`에서 실제 `20.016°` 떨어져 있다.  
  근거: [OwnershipVariantGenerator.cs:484](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipVariantGenerator.cs:484), [OwnershipVariantGenerator.cs:659](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipVariantGenerator.cs:659), [manifest_stated.json:603](<repo>/chatbot/tests/fixtures/ownership_v03/manifest_stated.json:603).  
  수정: 적용할 값으로 상한을 검사하고, 범위 내 양쪽 후보를 함께 평가해 목표와 대칭을 만족하는 최소 이동 쌍을 고른다.

- **중간 [3] → `lowVisibility=false`인 색 쌍도 배경 합성 후 변별 폭이 크게 줄어든다.**  
  재현: 위 색 쌍에서 blob의 불투명도만 `.15`로 낮추면 유효 판정이 유지된다. 코드의 중립 배경 합성식으로 계산한 ΔE는 약 `1.80/1.44`로, 유효성에 쓰인 알베도 ΔE `12.50/12.06`과 크게 다르다. 실제 지각 변별 여부는 추정이다.  
  근거: [OwnershipVariantGenerator.cs:313](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipVariantGenerator.cs:313), [OwnershipVariantGenerator.cs:673](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipVariantGenerator.cs:673), [OwnershipVariantGenerator.cs:735](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipVariantGenerator.cs:735).  
  수정: 알베도 대칭과 별도로 양쪽 합성 대비를 기록하고, 내부 시행에서 정한 변별 기준을 쌍 단위로 적용한다.

- **중간 [4·7] → Williams 표의 균형이 실제 배정 및 분석의 균형으로 이어지지 않는다.**  
  재현: 7조건 28명에서도 0부터 센 행 6은 P007·P021이 모두 `cb=0`이다. 같은 7조건이라도 색 쌍만 있는 세션과 크기 쌍만 있는 세션의 같은 행은 다른 자극을 뜻한다. 분석은 여전히 10행만 인정해 7·9조건의 행 10 이상을 미상으로 센다.  
  근거: [WilliamsDesign.cs:42](<repo>/unity/Assets/IFS/Runtime/Ownership/WilliamsDesign.cs:42), [WilliamsDesign.cs:71](<repo>/unity/Assets/IFS/Runtime/Ownership/WilliamsDesign.cs:71), [OwnershipVariantGenerator.cs:343](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipVariantGenerator.cs:343), [ownership.py:296](<repo>/chatbot/ifs_chatbot/eval/ownership.py:296).  
  수정: 실제 조건 집합별로 배정과 균형표를 만들고, 행을 한 주기 소진할 때마다 같은 행의 `cb`를 뒤집는다.

- **중간 [4] → 쌍을 꺼도 0.2의 실행과 기록이 재현되지 않는다.**  
  재현: `shiftAttributes=[]`만 설정하면 5조건 순서는 재현되지만 질문 기본값은 `resemblance`다. `mine`과 기존 문구를 지정해도 manifest 버전·필드와 CSV 헤더는 0.3이다. 고정 입력의 계획은 결정적이지만 실행 때 생성하는 manifest 전체는 시작 시각 등에 따라 바이트가 달라진다.  
  근거: [OwnershipConfig.cs:44](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipConfig.cs:44), [OwnershipRunner.cs:359](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipRunner.cs:359), [OwnershipManifest.cs:36](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipManifest.cs:36), [OwnershipRecordWriter.cs:68](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipRecordWriter.cs:68).  
  수정: 0.2 재현 모드가 필요하면 문항·문구·직렬화 버전을 함께 고정하고, 바이트 비교에는 동일한 세션 메타데이터를 넣는다.

- **중간 [6] → 여러 번 고른 뒤의 최종값이 설계상의 한 번 선택으로 쓰인다.**  
  재현: 색을 세 번 누르면 세 번째 색으로 라벨을 붙인다. 새로고침 후 다시 고르면 횟수는 1부터 시작한다. 크기는 중앙 `.5`에 손잡이가 보여 기준점을 주고, 초기 위치를 그대로 누르는 동작은 값을 확정하지 못한다. 색은 초기 선택점이 없다. `① → 값 선택 → ③`은 값 `null`을 저장하지만 이미 고른 경험은 남아 보조 ③ 집계에 섞인다.  
  근거: [prereport.js:92](<repo>/chatbot/ifs_chatbot/web/prereport.js:92), [prereport.js:150](<repo>/chatbot/ifs_chatbot/web/prereport.js:150), [prereport.js:182](<repo>/chatbot/ifs_chatbot/web/prereport.js:182), [prereport.js:229](<repo>/chatbot/ifs_chatbot/web/prereport.js:229), [ownership_shift.py:355](<repo>/chatbot/ifs_chatbot/eval/ownership_shift.py:355).  
  수정: 값 선택 전에 확정 여부를 잠그고, 미선택 상태에서 첫 의도적 선택을 기록하며, 재접속 시 문항 상태와 선택 이력을 복구한다.

- **중간 [5·6] → 철회 뒤에도 복제한 보고가 분석되고, 그 복제물이 Git에 들어갈 수 있다.**  
  재현: 보고를 Unity 기록이나 `chatbot/tests/fixtures/`에 복사한 후 철회하면 챗봇 원본만 지워진다. 복사본과 보고값 `p`를 담은 분석 CSV는 해당 경로에서 Git 무시 규칙에 걸리지 않는다. 이번에 추가된 fixture의 입력은 합성이다.  
  근거: [controller.py:391](<repo>/chatbot/ifs_chatbot/controller.py:391), [prereport.py:84](<repo>/chatbot/ifs_chatbot/prereport.py:84), [ownership.py:687](<repo>/chatbot/ifs_chatbot/eval/ownership.py:687), [.gitignore:1](<repo>/.gitignore:1), [OwnershipVariantTests.cs:574](<repo>/unity/Assets/IFS/Tests/Editor/OwnershipVariantTests.cs:574).  
  수정: 수동 복사 대신 저장소 밖 원본을 ID·해시로 조회하고, 철회 상태는 분석에서 강제하며, 실제 기록·출력의 커밋을 차단한다.

- **중간 [7] → shift가 기존 선택률·행동 상관에 들어가고 0쌍 분모도 달라진다.**  
  재현: 9조건에서 `size_hi`를 최종 선택하면 기존 다섯 선택률에 모두 0이 들어간다. 행동 상관에도 shift 네 행이 들어간다. `shiftAttributes=[]`인 재현 세션은 `disabled` 쌍만 있어도 Q1의 0쌍 분모에 들어간다. 반면 유효 쌍 1개인 참여자의 참여자 평균 포함과 `n=1`의 CI `null`·`lowN=true`는 설계에 맞다.  
  근거: [ownership.py:589](<repo>/chatbot/ifs_chatbot/eval/ownership.py:589), [ownership.py:611](<repo>/chatbot/ifs_chatbot/eval/ownership.py:611), [ownership.py:628](<repo>/chatbot/ifs_chatbot/eval/ownership.py:628), [ownership_shift.py:289](<repo>/chatbot/ifs_chatbot/eval/ownership_shift.py:289).  
  수정: 선택률과 상관의 제시 집합을 명시해 집계하고, Q1을 시행한 참여자로 0쌍 분모를 정한다.

### 낮음

- **낮음 [5] → 참여자에게 보이는 일부 고정 문구가 문구 버전의 관리 범위를 벗어난다.**  
  재현: ‘보기 전 보고로’, ‘이 세션의 보기 전 보고는 이미 받았습니다.’는 화면에 나오지만 버전·`status`·출처가 붙은 과제 파일에서 가져오지 않는다. 코드상 과제 답은 면담 질문·V1–V9·LLM·장면 생성에 전달되지 않으며, 제출 스키마는 ③의 값으로 `null`만 허용한다. 새 과제의 요청은 같은 서버의 상대 경로를 쓴다.  
  근거: [app.js:182](<repo>/chatbot/ifs_chatbot/web/app.js:182), [prereport.js:266](<repo>/chatbot/ifs_chatbot/web/prereport.js:266), [prereport_task.v0.json:63](<repo>/shared/protocol/prereport_task.v0.json:63), [prereport.v0.json:89](<repo>/shared/schemas/prereport.v0.json:89).  
  수정: 참여자용 링크·상태 문구를 과제 파일로 옮겨 `status`와 출처를 붙이고 버전을 올린다.

- **낮음 [6·7] → 제출과 분석의 검증 범위가 달라 파일 하나가 분석을 멈출 수 있다.**  
  재현: 나머지는 정상인 보고에 `altSpecSha256: ["x"]`를 넣으면 서버 스키마는 거부하지만 파일 분석은 `.values()`에서 중단된다. 해시 불일치 보고는 제외 사유에는 남지만 보조 하락량에서는 실제 미제출과 같은 `no_report`에 섞인다.  
  근거: [prereport.v0.json:15](<repo>/shared/schemas/prereport.v0.json:15), [ownership_shift.py:80](<repo>/chatbot/ifs_chatbot/eval/ownership_shift.py:80), [ownership_shift.py:121](<repo>/chatbot/ifs_chatbot/eval/ownership_shift.py:121), [ownership_shift.py:336](<repo>/chatbot/ifs_chatbot/eval/ownership_shift.py:336).  
  수정: 분석에서 같은 스키마를 검증하고 미제출·형식 오류·연결 실패를 별도 집계한다.

- **낮음 [6] → X43의 사후 질문 세 가지가 수집되지 않는다.**  
  재현: 마지막 선택과 선택적 차이 평정을 마치면 종료 문구가 나오며 판단 기준·목적 추측·심상 변화 응답을 남길 단계가 없다.  
  근거: [decisions.md:201](<repo>/docs/decisions.md:201), [OwnershipRunner.cs:647](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipRunner.cs:647), [OwnershipRunner.cs:700](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipRunner.cs:700).  
  수정: 원본을 알려 주는 차이 평정 전에 버전이 붙은 사후 문항을 수집한다.

- **낮음 [8] → 현재 테스트의 합격 조건이 일부 결함을 그대로 허용한다.**  
  재현: 혼합 버전 테스트는 기존 RQ에 `n=2`가 들어가야 통과하고, Unity fixture 테스트는 해시 `"0"`으로 라벨이 붙어야 통과한다. 구버전 골든 테스트는 새 필드를 제거하고 버전을 바꾼 JSON만 비교한다. 브라우저 테스트는 파일 제공 여부만 본다.  
  근거: [test_ownership_shift.py:246](<repo>/chatbot/tests/test_ownership_shift.py:246), [test_ownership_shift.py:282](<repo>/chatbot/tests/test_ownership_shift.py:282), [OwnershipVariantTests.cs:655](<repo>/unity/Assets/IFS/Tests/Editor/OwnershipVariantTests.cs:655), [test_prereport.py:157](<repo>/chatbot/tests/test_prereport.py:157).  
  수정: ① 직선·원형 거리 등호 ② 두 크기 눈금의 부호 반전 ③ 0.2/0.3 및 두 문항 집계 ④ 7조건 두 주기의 행×`cb` ⑤ 브라우저에서 재선택·새로고침·제시 후 제출 차단을 검증한다.