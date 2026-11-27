1. **[고쳐짐]** 부정 표지의 범위와 개수를 구분하고, 이중 부정은 값을 비우도록 바뀌었습니다([resay.py](<repo>/chatbot/ifs_chatbot/resay.py:288), [시험](<repo>/chatbot/tests/test_g73_resay_mapping.py:116)). 재현 입력 `안개가 안 보이지는 않아요` → `material.opacity` 미지정, `notRead.reason=double_negation`.

2. **[고쳐짐]** 판정 불가 중심 명사가 하나라도 있으면 다른 명사 판정 여부와 관계없이 생성이 차단됩니다([resay.py](<repo>/tools/gen3d/resay.py:132), [시험](<repo>/tools/gen3d/tests/test_g73_resay.py:189)). 재현 입력 `미지사물, 둥근 덩어리` → `blocked`, 사유 `unjudged_head_noun`, 생성 호출 0회.

3. **[고쳐짐]** 디렉터리 안 파일을 상대 경로 순으로 정렬해 내용 해시를 계산합니다([wordnet_filter.py](<repo>/tools/gen3d/wordnet_filter.py:26), [시험](<repo>/tools/gen3d/tests/test_g73_resay.py:345)). 재현 조건: 내용이 같은 WordNet 폴더를 다른 파일 생성 순서·위치에 두면 같은 SHA-256, 파일 내용 변경 시 다른 해시.

**새 문제:** 이 커밋이 만든 문제는 확인하지 못했습니다. 알려 주신 `안개가 안 보여요` 사례는 공유 로직 문제로 제외했습니다.