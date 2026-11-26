# CP6 — CP5 높음 지적의 수정 확인 (Codex)

- 일시: 2026-11-18
- 호출: `codex exec --sandbox read-only -c model_reasoning_effort="medium"` (RQ v2 작업 3/3회)
- 프롬프트: `docs/codex-reviews/prompts/CP6_prompt.md`
- 검토 대상: 커밋 `562bd72..2d26728`의 `unity/`, `chatbot/`, `shared/`, `.gitignore`
- 판정(수용/반박/보류)은 `docs/decisions.md`에 적습니다.

---

1. **덜 고쳐짐**  
   정상 0.2 기록과 `mine` 세션은 Q1에서 빠지고, 기존 RQ도 문항별로 집계된다. 다만 `recordVersion=ifs-ownership/0.2`인 manifest에 `ratingItem=resemblance`를 추가하고 CSV의 `item`도 맞추면 기존 RQ에서 0.3과 평균된다. 유효한 `shiftPairs`와 대응 제시·평정·보고까지 붙이면 Q1에도 들어간다. 버전 판별이 `recordVersion` 대신 필드 유무에 의존한다. [ownership.py:175](<repo>/chatbot/ifs_chatbot/eval/ownership.py:175), [ownership.py:584](<repo>/chatbot/ifs_chatbot/eval/ownership.py:584), [ownership.py:758](<repo>/chatbot/ifs_chatbot/eval/ownership.py:758)  
   수정은 `recordVersion`으로 문항 규칙을 정하고, 0.1·0.2에서 0.3 전용 필드가 발견되면 경고와 함께 격리하는 것이다.

2. **덜 고쳐짐**  
   두 값은 모두 가로 길이(m)다. 웹은 원 지름, Unity는 자세가 적용된 최대 가로 폭이다. `lying`, `s=.5`에서 각각 `.35 m`와 `.455 m`이므로 같은 막대값의 물리적 의미는 다르다. 물리 폭 경로의 `too_close`는 두 `log₂` 이동 거리 중 작은 값의 절반을 양의 문턱으로 쓴다. 단위는 `log₂` 폭 비율이고, 대비는 `near − far`다. [prereport.js:131](<repo>/chatbot/ifs_chatbot/web/prereport.js:131), [RenderedSize.cs:44](<repo>/unity/Assets/IFS/Runtime/SceneSpec/RenderedSize.cs:44), [ownership_shift.py:213](<repo>/chatbot/ifs_chatbot/eval/ownership_shift.py:213), [ownership_shift.py:325](<repo>/chatbot/ifs_chatbot/eval/ownership_shift.py:325)  
   재현 `posture=none`, `w/lo/hi=.5/.4/.6`, 보고 `.45`. 정확한 로그 거리에서는 원본과 `lo`가 등거리지만, 기록 폭 `.3500/.2653/.4618/.3047 m`를 다시 로그 양자화하면 `size_lo`가 채택된다. 수정은 폭 기록 정밀도를 높이고 기록 정밀도에서 구분할 수 없는 거리 차이를 제외하는 것이다. [OwnershipVariantGenerator.cs:784](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipVariantGenerator.cs:784), [ownership_shift.py:132](<repo>/chatbot/ifs_chatbot/eval/ownership_shift.py:132)  
   재현 `stated`, `w=.47996`, `sizeShiftStep=.02`. 반올림 전 `hi=.49996`으로 범주 검사를 통과하지만 실제 적용값은 `.5000`이다. 수정은 원본의 반올림 전 값과 실제 적용할 끝값으로 같은 쪽인지 검사하는 것이다. [OwnershipVariantGenerator.cs:787](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipVariantGenerator.cs:787)

3. **덜 고쳐짐**  
   실제 제출 `02:00:00`, 제시 `02:00:05`에 서버 시계가 10초 빠르면 정상 보고가 제외된다. 반대로 실제 제시 5초 뒤 제출에 서버가 10초 느리면 통과한다. 정상 출력은 UTC `Z`이고 명시적 오프셋은 UTC로 환산되지만, Unity 이벤트의 시간대 없는 문자열과 날짜만 있는 문자열도 UTC로 해석된다. 밀리초가 같으면 제외된다. 수정은 보고 접수와 제시 허가의 순서를 같은 시스템에서 기록하고, 시각 비교에는 오프셋이 명시된 타임스탬프만 허용하는 것이다. [prereport.py:57](<repo>/chatbot/ifs_chatbot/prereport.py:57), [OwnershipRunner.cs:465](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipRunner.cs:465), [ownership_shift.py:88](<repo>/chatbot/ifs_chatbot/eval/ownership_shift.py:88), [ownership_shift.py:181](<repo>/chatbot/ifs_chatbot/eval/ownership_shift.py:181)  
   `requirePrereport` 경로에서 선택값·확정 여부는 자극·순서·화면에 쓰이지 않는다. 계획 생성 뒤 보고를 읽고 실험자 화면에 연결 상태만 표시한다. [OwnershipRunner.cs:294](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipRunner.cs:294), [OwnershipExperimenterGui.cs:85](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipExperimenterGui.cs:85)

4. **덜 고쳐짐**  
   정상 생성된 주 파일과 v0·v1 파일은 보고와 같은 `sessionId`를 갖는다. 메타 ID가 `null`이면 Unity는 파일 이름을 쓰므로 `S.v0.json`은 `S.v0`이 된다. 주 파일을 바이트 그대로 복사하면 확정 시 해시와 일치한다. LF↔CRLF 변환이나 JSON 재직렬화는 해시를 바꾼다. Unity의 보고 복사본과 manifest의 보고 해시는 같은 원본 바이트에서 나온다. [controller.py:842](<repo>/chatbot/ifs_chatbot/controller.py:842), [controller.py:895](<repo>/chatbot/ifs_chatbot/controller.py:895), [prereport.py:62](<repo>/chatbot/ifs_chatbot/prereport.py:62), [OwnershipRunner.cs:278](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipRunner.cs:278), [OwnershipRunner.cs:400](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipRunner.cs:400), [OwnershipPrereport.cs:41](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipPrereport.cs:41), [OwnershipRecordWriter.cs:140](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipRecordWriter.cs:140)  
   재현 `save_both=true`, 주 매핑 v1, `requirePrereport=true`에서 정상 제출 뒤 바이트 그대로의 `S.v0.json`을 고른다. 분석기는 대체 해시를 인정하지만 Unity는 주 해시만 검사해 시작을 거부한다. 반대로 분석기는 manifest의 보고 해시를 지우면 복사본 해시 검사를 건너뛴다. 수정은 Unity와 분석기에 동일한 주·대체 해시 및 세션 ID 규칙을 적용하고, 새 기록에는 보고 파일 해시를 필수로 두는 것이다. [OwnershipPrereport.cs:50](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipPrereport.cs:50), [OwnershipPrereport.cs:72](<repo>/unity/Assets/IFS/Runtime/Ownership/OwnershipPrereport.cs:72), [ownership_shift.py:170](<repo>/chatbot/ifs_chatbot/eval/ownership_shift.py:170)  
   재현 Unity 기록을 만든 뒤 챗봇에서 철회하면 남은 복사본은 계속 분석된다. 분석 `summary.json`만 기록 폴더 밖에 복사하면 새 Git 무시 규칙도 적용되지 않는다. 수정은 철회 ID를 분석에서 강제하고, 분석 출력은 저장소 밖에 쓰도록 하는 것이다. [controller.py:393](<repo>/chatbot/ifs_chatbot/controller.py:393), [ownership.py:767](<repo>/chatbot/ifs_chatbot/eval/ownership.py:767), [.gitignore:5](<repo>/.gitignore:5)

5. **새 결함**  
   재현 크기 막대 첫 접촉이 `pointercancel`로 끝난 뒤 정상 선택을 한다. 취소된 값이 `firstValue`로 남아 주 분석에 쓰인다. 수정은 `pointerup`에서만 선택을 확정하고 취소 시 마지막 확정값을 복원하는 것이다. [prereport.js:182](<repo>/chatbot/ifs_chatbot/web/prereport.js:182), [prereport.js:333](<repo>/chatbot/ifs_chatbot/web/prereport.js:333)  
   재현 ②에서 값을 고르고 [답 바꾸기]로 ①을 확정한 뒤 진행한다. 변경 표시는 남지만 ②에서 고른 값이 ① 주 분석에 들어간다. 수정은 선택 당시 확정 여부를 기록하고 확정 여부가 바뀐 쌍을 주 분석에서 빼는 것이다. [prereport.js:264](<repo>/chatbot/ifs_chatbot/web/prereport.js:264), [ownership_shift.py:410](<repo>/chatbot/ifs_chatbot/eval/ownership_shift.py:410)  
   재현 `lying`, `w/lo/hi=.5/.4/.6`, 보고 `.56`. 0.1 보고의 최종값은 첫 선택으로 대체되어 정규화 눈금에서 `size_hi`로 집계되고, 같은 값의 0.2 보고는 물리 폭 경로에서 `too_close`로 제외된다. 수정은 0.1 보고를 별도 보조 집계로 두고, 주 분석에는 관측된 첫 선택과 물리 폭이 있는 쌍을 쓰는 것이다. [ownership_shift.py:191](<repo>/chatbot/ifs_chatbot/eval/ownership_shift.py:191), [ownership_shift.py:213](<repo>/chatbot/ifs_chatbot/eval/ownership_shift.py:213), [ownership_shift.py:446](<repo>/chatbot/ifs_chatbot/eval/ownership_shift.py:446)  
   0.2 무채색 `h:null`은 스키마와 Unity 바이트 복사를 통과한다. 분석기는 명도 쌍에서 `l`을 쓰고 색상각 쌍에서는 `report_axis_mismatch`로 제외한다. 5조건은 기존 10행 표와 같은 `cb` 식을 사용한다. [prereport.v0.2.json:87](<repo>/shared/schemas/prereport.v0.2.json:87), [ownership_shift.py:224](<repo>/chatbot/ifs_chatbot/eval/ownership_shift.py:224), [WilliamsDesign.cs:37](<repo>/unity/Assets/IFS/Runtime/Ownership/WilliamsDesign.cs:37), [WilliamsDesign.cs:80](<repo>/unity/Assets/IFS/Runtime/Ownership/WilliamsDesign.cs:80)

**내부 시행 전에 반드시 고칠 것**

- 보고 접수와 첫 제시의 순서를 동일한 기준으로 검증한다.
- Unity와 분석기의 보고 연결 규칙을 일치시키고 철회된 사본을 분석에서 제외한다.
- 취소·확정 여부 변경·0.1 대체값이 주 분석의 첫 선택으로 들어가는 경로를 닫는다.