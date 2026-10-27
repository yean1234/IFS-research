from ifs_chatbot.korean import Analyzer, count_questions, josa, mask_quoted, normalize, quoted_spans, squash


def test_josa_by_final_consonant():
    assert josa("덩어리", "은/는") == "는"
    assert josa("회색", "은/는") == "은"
    assert josa("바닥", "와/과") == "과"
    assert josa("종이", "와/과") == "와"
    assert josa("돌", "으로/로") == "로"      # ㄹ 받침은 '로'
    assert josa("ABC", "은/는") == "은(는)"   # 판단 불가면 병기


def test_normalize_quotes_and_spaces():
    assert normalize("그  ‘덩어리’는？ ") == "그 '덩어리'는?"
    assert squash("젖은  종이") == "젖은종이"


def test_quoted_spans_and_mask():
    utt = "그 '회색'은 마치 무엇 같나요?"
    assert quoted_spans(utt) == ["회색"]
    assert mask_quoted(utt) == "그 QQ은 마치 무엇 같나요?"
    assert count_questions("더 있나요? 어디에 있나요?") == 2


def test_mask_keeps_particle_as_particle():
    # 따옴표를 그냥 지우면 '은'이 명사(銀)로 분석돼 V5가 오탐했다(회귀 테스트)
    a = Analyzer()
    assert "은" not in a.content_lemmas(mask_quoted("그 '회색'은 마치 무엇 같나요?"))
