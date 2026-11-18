너는 이 연구 저장소의 독립 코드 검토자다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라. 칭찬과 요약 서론은 생략하고, 결과를 틀리게 만드는 결함을 찾아라.

## 검토 대상
커밋 `f5b4e69..HEAD`의 구현 변경(`git diff f5b4e69..HEAD -- unity chatbot shared`). 설계는 `docs/rq-v2-proposal.md` 3.1–3.2·7절, 판정은 `docs/decisions.md` X36–X47.

- Unity(C#): `unity/Assets/IFS/Runtime/Ownership/`의 양쪽 변형(color_lo/hi, size_lo/hi), 쌍 유효성(`shiftPairs`), n조건 Williams 순서, 가변 길이 러너·기록, '닮았다' 문항, `unity/Assets/StreamingAssets/IFS/ownership_task.v0.2.json`.
- Python·웹: `chatbot/ifs_chatbot/prereport.py`, `chatbot/ifs_chatbot/web/prereport.{html,js}`, `chatbot/ifs_chatbot/server.py`·`controller.py`의 보기 전 보고 과제, `chatbot/ifs_chatbot/eval/ownership_shift.py`와 `ownership.py`의 분석, `shared/schemas/prereport.v0.json`, `shared/protocol/prereport_task.v0.json`.

## 이미 알고 있는 것 (되풀이하지 말 것)
- Unity 에디터와 Quest 3 실기에서는 한 번도 돌리지 못했다. dotnet compile-check(스텁)와 pytest로만 확인했다.
- 전체 pytest를 한 프로세스로 돌리면 `test_e2e`의 메모리 사용으로 이 환경에서 중단된다(이번 변경과 무관).
- 이동폭(크기 ±0.10, 색 ΔE00 12, 색상 상한 20°, 대칭 허용 ΔE 3)은 근거 없는 잠정값이고 내부 시행으로 정한다.
- Q1 결론은 "보고값에 가까운 형상을 더 닮았다고 평정하는가"까지이고 보고값 기억은 가르지 못한다(X36).
- `prereport.json`은 챗봇 로그 폴더에 쓰이고, 분석하려면 Unity 기록 폴더로 옮겨야 한다. 색 선택 면은 채도가 고정이라 회색을 고를 수 없다. 이 둘은 알고 있으니, 더 나은 처리 방법이 있으면 한 줄로만 적어라.

## 찾아 달라는 것
1. **가까운·먼 판정의 정확성**(`ownership_shift.py`): 색상 감김, lo/hi의 각도가 다른 경우, p가 w의 반대편 180° 근처인 경우, 조건 `d(가까운,p) < d(w,p) < d(먼,p)`의 구현, too_close 문턱, basis 판정. 틀린 부호나 뒤집힌 라벨이 나오는 입력을 구체적으로 제시하라.
2. **생성기와 분석기의 계약 어긋남**: manifest `shiftPairs`·variants·`ratingItem`·ratings.csv `item`의 필드 이름·단위·null 처리에서 C#이 쓰는 것과 Python이 읽는 것이 다른 곳(파일:줄 양쪽).
3. **쌍 유효성 규칙**(`OwnershipVariantGenerator.cs`): 범위·낱말 범위·대칭 판정의 빈틈, 한쪽만 보여 주게 되는 경로, 말한 크기가 0.5 근처일 때, 색 basis mixed, lowVisibility.
4. **결정성과 재현성**: 같은 입력에서 manifest가 바이트까지 같은가. 0.2 기록(5조건)의 재현이 깨지는 곳. n조건 Williams 설계의 균형과 참여자 번호 → 행 배정.
5. **원칙 위반**(AGENTS.md 1·2·3·5·6·7): 보기 전 보고 과제가 면담 프로토콜·검증기를 건드리는지, ③에 값이 저장될 수 있는 경로, 고른 값이 장면 JSON으로 새는 경로, 문구 status·출처·버전, 외부 요청, 참여자 자료가 git에 들어갈 수 있는 경로(fixture 포함).
6. **보기 전 보고 과제의 측정 타당도를 해치는 구현**: 다시 고르기 허용과 횟수 기록, 막대·색 면의 초기 상태가 답을 유도하는지, 확정 전 접근·중복 제출·철회 처리, spec 해시 연결.
7. **분석기의 통계 처리**: 참여자별 평균과 CI 계산, 쌍이 1개인 참여자, n이 작을 때 표시, 0.2·0.3 기록을 섞어 읽을 때, mismatch 분석이 shift 변형에 오염되는지.
8. **테스트의 빈틈**: 통과하지만 실제 결함을 못 잡는 테스트, 빠진 사례 최대 5개.

## 출력 형식
- 결함마다: 심각도(높음/중간/낮음) → 한 줄 요약 → 재현 입력이나 시나리오 → 근거 파일:줄 → 고칠 방법 한 줄.
- 심각도 높은 것부터. 확신이 없는 것은 "추정"이라고 표시.
- 문제를 못 찾은 항목은 번호와 "문제 못 찾음"만.
- 전체 120줄 이내.
