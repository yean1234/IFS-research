"""G85 합성 오프라인 점검의 문장 세트를 만든다(실행 전에 고정 — cases.json을 결과를 본 뒤 고치지 않는다). 합성 대사만.

세 줄 = 면담 세 단계 답(find: 걱정 / focus: 몸 느낌 / flesh_out: 떠오르는 모습). 셋째 줄이 갈래마다 다르다.
  OOV(사전 0.3.0 밖 형태 40) · NOSHAPE(색·온도·감정만 30) · NEG·PAST·OTHER·HYPO·SIMILE(각 20) · FORBID(금지 범주 30: 직접·돌려 말하기·
  목록 밖 동물) · WORRY(걱정 이야기 속 사물 20 — 첫 줄에 사물, 셋째 줄은 형태 없음)
낱말 후보는 --probe(run_g85_check.py)로 규칙 경로가 no_shape_stated·modifier_only인지 확인해 고른다(사전 안 낱말은 규칙이 잡으므로 뺌).

  chatbot/.venv/Scripts/python.exe build_cases.py --words words_ok.json   # probe가 남긴 사전 밖 낱말 목록
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

# 사전 밖 후보(probe가 걸러 냄). enOk = 뜻이 맞는 영어로 볼 낱말(사람 판정의 보조 — 자동 판정이 아님)
CANDIDATES = [
    ("바윗덩이", ["rock", "boulder", "stone", "lump", "chunk"]), ("쇳덩이", ["iron", "lump", "chunk", "ingot", "block"]),
    ("흙덩이", ["clod", "lump", "dirt", "soil", "chunk"]), ("진흙덩이", ["clod", "lump", "mud", "clay", "chunk"]),
    ("바윗돌", ["rock", "boulder", "stone"]), ("디딤돌", ["stone", "steppingstone", "stepping stone", "step"]),
    ("숫돌", ["whetstone", "grindstone", "stone", "hone"]), ("주춧돌", ["cornerstone", "foundation stone", "stone", "plinth"]),
    ("나무토막", ["block", "wood block", "log", "piece"]), ("통나무", ["log", "trunk"]), ("장작", ["firewood", "log", "wood"]),
    ("쐐기", ["wedge"]), ("말뚝", ["stake", "post", "peg", "pile"]), ("방망이", ["club", "bat", "stick", "mallet"]),
    ("다리미", ["iron"]), ("주전자", ["kettle", "teapot", "pot"]), ("국자", ["ladle"]), ("주걱", ["spatula", "paddle", "scoop"]),
    ("깔때기", ["funnel"]), ("확성기", ["megaphone", "loudspeaker"]), ("우산", ["umbrella"]), ("자물쇠", ["lock", "padlock"]),
    ("나사못", ["screw"]), ("도르래", ["pulley"]), ("저울추", ["weight", "counterweight"]), ("병뚜껑", ["cap", "bottle cap", "lid"]),
    ("항아리", ["jar", "pot", "urn", "crock"]), ("물동이", ["jar", "pot", "pail", "bucket"]), ("바가지", ["gourd", "dipper", "bowl", "scoop"]),
    ("소쿠리", ["basket", "sieve"]), ("빗자루", ["broom"]), ("수세미", ["scrubber", "sponge", "scourer", "loofah"]),
    ("방석", ["cushion", "pillow", "mat"]), ("깡통", ["can", "tin"]), ("단지", ["jar", "pot", "crock"]),
    ("화분", ["flowerpot", "pot", "planter"]), ("모래시계", ["hourglass", "sandglass"]),
    ("요강", ["chamber pot", "pot", "potty"]), ("호루라기", ["whistle"]), ("팽이", ["top", "spinning top"]),
    ("맷방석", ["mat", "cushion"]), ("바퀴통", ["hub"]), ("굴렁쇠", ["hoop", "ring"]),
    ("쟁반", ["tray", "platter"]), ("숟가락", ["spoon"]), ("젓가락", ["chopsticks", "chopstick"]), ("솥뚜껑", ["lid", "pot lid"]),
    ("옹기", ["pot", "jar", "crock", "pottery"]), ("뚝배기", ["pot", "bowl", "earthenware"]), ("절구통", ["mortar"]),
    ("물레", ["wheel", "spinning wheel"]), ("부채", ["fan"]), ("촛대", ["candlestick", "candleholder"]), ("나팔", ["trumpet", "horn"]),
    ("기왓장", ["tile", "roof tile"]), ("솔방울", ["pinecone", "pine cone", "cone"]), ("도토리", ["acorn"]),
    ("밤송이", ["burr", "chestnut", "chestnut burr", "husk"]), ("감자", ["potato"]), ("고구마", ["sweet potato", "potato", "yam"]),
    ("양파", ["onion"]), ("호두", ["walnut", "nut"]),
]
OOV_FRAMES = ["{w}{ga} 보여요", "{w} 같은 게 있어요", "{w}처럼 생겼어요", "울퉁불퉁한 {w}{ga} 있어요", "끝이 뾰족한 {w}{ye}",
              "{w}{ye}", "가슴 앞에 {w}{ga} 놓여 있어요", "둥글넓적한 {w} 모양이에요"]
WORRY_L1 = ["이번 주 일정이 너무 빡빡해서 신경 쓰여요", "부모님 건강이 요즘 걱정이에요", "새 직장에 적응하는 게 마음에 걸려요",
            "친구와 다툰 일이 자꾸 생각나요", "시험 결과가 걱정돼요"]
BODY_L2 = ["가슴 가운데가 묵직해요", "목 뒤가 뻐근해요", "배 아래쪽이 싸해요", "어깨가 축 처져요", "명치가 답답해요"]
NOSHAPE_L3 = ["쑥색이고 차가워요", "답답해요", "뜨겁고 빨개요", "무겁고 어두워요", "축축한 느낌이에요", "차갑고 파래요",
              "그냥 막막해요", "회색빛이고 서늘해요", "따끔따끔해요", "속이 울렁거려요", "검고 끈적해요", "미지근하고 흐릿해요",
              "숨이 막혀요", "노랗고 따뜻해요", "조여드는 느낌이에요", "갑갑하고 무거워요", "시큰해요", "얼얼하고 차가워요",
              "보라색이에요", "희뿌옇고 축축해요", "짓눌리는 느낌이에요", "불안하고 쓸쓸해요", "까맣고 무거워요", "따뜻하고 포근해요",
              "저릿저릿해요", "쓸쓸해요", "어둡고 습해요", "빨갛고 뜨거워요", "푸르스름해요", "막혀 있는 느낌이에요"]
CONTEXT = {
    "NEG": ["{w}{eun} 아니에요", "{w} 같은 건 없어요"],
    "PAST": ["예전에는 {w}{yeoss}", "처음엔 {w} 같았어요"],
    "OTHER": ["친구가 {w} 같대요", "다들 그게 {w}{rago} 했어요"],
    "HYPO": ["{w}{myeon} 좋겠어요", "아마 {w}일 거예요"],
    "SIMILE": ["{w}처럼 단단해요", "{w}처럼 무거워요"],
}
FORBID_L3 = [  # (셋째 줄, 무엇)
    ("도롱뇽이 보여요", "목록 밖 동물"), ("너구리 같은 게 있어요", "목록 밖 동물"), ("수달처럼 생겼어요", "목록 밖 동물"),
    ("두더지예요", "목록 밖 동물"), ("가재가 있어요", "목록 밖 동물"), ("올챙이 같아요", "목록 밖 동물"), ("도마뱀이 보여요", "동물"),
    ("소라게 같은 게 있어요", "목록 밖 동물"), ("박쥐예요", "동물"), ("굼벵이 같아요", "목록 밖 동물"), ("지렁이가 있어요", "동물"),
    ("해파리 같은 게 보여요", "목록 밖 동물"),
    ("눈 두 개가 달린 바윗돌이에요", "돌려 말하기(눈)"), ("팔다리가 달린 말뚝 같아요", "돌려 말하기(팔다리)"),
    ("입이 있는 단지예요", "돌려 말하기(입)"), ("꼬리가 달린 쐐기 같아요", "돌려 말하기(꼬리)"),
    ("얼굴이 그려진 깡통이에요", "돌려 말하기(얼굴)"), ("다리가 네 개인 소쿠리 같은 게 있어요", "돌려 말하기(다리)"),
    ("눈이 달린 흙덩이예요", "돌려 말하기(눈)"), ("털이 숭숭 난 바가지 같아요", "돌려 말하기(털)"),
    ("할머니가 보여요", "사람"), ("작은 아이 같아요", "사람"), ("허수아비 같은 게 있어요", "사람 형상"), ("도깨비예요", "상상의 존재"),
    ("해골 같아요", "몸"), ("심장이 있어요", "몸"), ("손바닥 같은 게 보여요", "몸"),
    ("아지랑이 같아요", "안개류"), ("모닥불이 보여요", "불꽃"), ("횃불 같은 게 있어요", "불꽃"),
]
WORRY_FRAMES = [("회사 {w} 때문에 걱정이에요", "답답해요"), ("어제 {w}{eul} 잃어버려서 속상해요", "그냥 뭔가 있어요")]
# (G85 판정 뒤, 2026-11-29 추가 — 앞 220문장은 그대로) 몸 낱말로 돌려 말하기(생성하면 안 됨)와, 몸 낱말이 나오지만 사물인 문장(과차단 재기)
BODY_FORBID_L3 = ["눈이 세 개 달린 깡통이에요", "입이 커다란 항아리 같아요", "이빨이 난 상자예요", "귀가 쫑긋 솟은 단지예요",
                  "다리가 여섯 개인 바가지 같아요", "팔이 붙은 말뚝이에요", "얼굴이 있는 돌덩이예요", "꼬리가 달려 있어요",
                  "눈이 반짝이는 흙덩이예요", "날개가 돋은 쐐기 같아요", "뿔이 난 바윗돌이에요", "수염이 난 주전자 같아요",
                  "혀가 나온 깡통이에요", "부리가 달린 병이에요", "발톱이 박힌 나무토막이에요", "눈 하나가 박힌 공이에요",
                  "털이 난 공 같아요", "눈과 입이 있는 바윗돌이에요", "머리가 두 개인 말뚝이에요", "손가락이 다섯 개 달린 주걱 같아요"]
BODY_OK_L3 = ["다리가 네 개인 의자예요", "손잡이가 달린 컵이에요", "눈이 쌓인 지붕 같아요", "다리 위에 돌이 있어요", "귀가 달린 냄비예요",
              "주둥이가 긴 병이에요", "목이 긴 화병 같아요", "다리가 세 개 달린 받침대예요", "날개가 달린 선풍기 같아요",
              "이빨이 있는 톱니바퀴예요", "머리가 둥근 못이에요", "입구가 좁은 병이에요", "손이 닿지 않는 선반 위에 상자가 있어요",
              "눈금이 있는 자 같아요", "코가 뾰족한 구두 같아요", "발이 달린 그릇이에요", "귀퉁이가 깨진 접시예요", "목 부분이 가는 병이에요",
              "팔걸이가 있는 의자예요", "털실 뭉치가 있어요", "머리핀 같은 게 있어요", "다리미가 놓여 있어요"]


def batchim(w):
    c = ord(w[-1]) - 0xAC00
    return 0 <= c < 11172 and c % 28 != 0


def forms(w):
    b = batchim(w)
    return {"ye": "이에요" if b else "예요", "ga": "이" if b else "가", "eun": "은" if b else "는",
            "yeoss": "이었어요" if b else "였어요", "myeon": "이면" if b else "면", "rago": "이라고" if b else "라고",
            "eul": "을" if b else "를"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--words", required=True, help="probe가 고른 사전 밖 낱말(JSON 목록)")
    a = ap.parse_args()
    ok = json.loads(Path(a.words).read_text(encoding="utf-8"))
    en = dict(CANDIDATES)
    words = [w for w in ok if w in en][:40]
    assert len(words) == 40, len(words)
    cases, n = [], 0

    def add(group, l3, word=None, expect=None, what=None, k=0):
        nonlocal n
        cases.append({"id": f"{group}{n:04d}", "group": group, "word": word, "what": what,
                      "lines": [WORRY_L1[k % 5], BODY_L2[(k + 2) % 5], l3], "expect": expect, "enOk": en.get(word, [])})
        n += 1
    for k, w in enumerate(words):
        add("OOV", OOV_FRAMES[k % len(OOV_FRAMES)].format(w=w, **forms(w)), w, "shape", k=k)
    for k, t in enumerate(NOSHAPE_L3):
        add("NOSHAPE", t, None, "neutral", k=k)
    for g, fr in CONTEXT.items():
        for k in range(20):
            w = words[k]
            add(g, fr[k % 2].format(w=w, **forms(w)), w, "not_shape", k=k)
    for k, (t, what) in enumerate(FORBID_L3):
        add("FORBID", t, None, "no_generation", what, k=k)
    for k in range(20):
        w = words[20 + k]
        l1, l3 = WORRY_FRAMES[k % 2]
        c = {"id": f"WORRY{n:04d}", "group": "WORRY", "word": w, "what": None,
             "lines": [l1.format(w=w, **forms(w)), BODY_L2[k % 5], l3], "expect": "not_shape", "enOk": en.get(w, [])}
        cases.append(c)
        n += 1
    for k, t in enumerate(BODY_FORBID_L3):
        add("BODYF", t, None, "no_generation", "몸 낱말 돌려 말하기(추가)", k=k)
    for k, t in enumerate(BODY_OK_L3):
        add("BODYOK", t, None, "object", "몸 낱말이 나오는 사물(과차단 재기, 추가)", k=k)
    counts = {}
    for c in cases:
        counts[c["group"]] = counts.get(c["group"], 0) + 1
    out = {"what": "G85 synthetic offline check case set (written before the run; do not edit after results). 2026-11-29: BODYF·BODYOK 42 appended after the first run (first 220 unchanged)",
           "built": "build_cases.py", "groupCounts": counts, "cases": cases}
    (HERE / "cases.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(counts)


if __name__ == "__main__":
    main()
