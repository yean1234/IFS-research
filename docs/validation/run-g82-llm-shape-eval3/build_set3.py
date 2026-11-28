"""G82 3차 평가 문장 세트(합성 대사만, 참여자 자료 아님). 실행 전에 cases.json으로 고정하고 결과를 본 뒤 고치지 않는다.

1·2차 세트·프롬프트 0.3.0의 예시 낱말(구두주걱·맷돌·벽돌)과 겹치지 않는 낱말을 쓰고, 2차 세트와 같은 확정 텍스트가 나오면 뺀다.
문장 하나 = 정적 면담의 답 세 줄 [찾기 단계(신경 쓰는 일), 머물기 단계(느낌), 구체화 단계(모습)] — 고치지 않으므로 단계 표지를 얻는다.

갈래: P 사전 밖 형태(enOk = 허용 번역, 실행 전 고정) · SIMILE 속성 비유 200(비유 뒤 서술어 품사 4갈래 VA·XR·VV·MAG 각 50) ·
NEG·PAST·OTHER·HYPO·PERSON·ANIMAL·MIST·NONE·WORRY 각 50. 차단 갈래는 틀 10개 이상 × 낱말 목록.
실행: python build_set3.py → cases.json
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "run-g82-llm-shape-eval2"))
from build_set import J, NEG, OTHER, PAST, HYPO, batchim  # noqa: E402  (조사 붙이기·차단 틀은 2차와 같은 함수 — 낱말이 달라 문장이 다르다)

WORRY_PLAIN = ["이번 주 일정이 너무 빡빡해서 신경 쓰여요", "부모님 건강이 요즘 걱정이에요", "새 직장에 적응하는 게 마음에 걸려요",
               "시험 결과가 나올 때까지 초조해요", "연락이 끊긴 친구가 계속 생각나요", "이번 달 생활비가 빠듯해서 걱정이에요",
               "곧 있을 면접이 제일 신경 쓰여요", "동아리 일로 사람들과 부딪혀서 마음이 불편해요", "잠을 잘 못 자서 걱정이에요",
               "계획한 일이 자꾸 미뤄져서 답답해요"]
FEEL = ["가슴 가운데가 묵직해요", "목 뒤가 뻐근해요", "배 아래쪽이 싸해요", "어깨가 축 처져요", "명치 쪽이 답답해요",
        "등 위쪽이 굳어 있어요", "관자놀이가 지끈거려요", "손바닥이 축축해요", "가슴 왼쪽이 저릿해요", "속이 울렁거려요"]

P_WORDS = [
    ("프라이팬", ["pan", "frypan", "skillet"]), ("도마", ["cuttingboard", "board", "chopboard"]), ("물통", ["bottle", "canteen", "jug", "flask"]),
    ("돋보기", ["magnifier"]), ("저금통", ["piggybank", "moneybox", "bank"]), ("액자", ["frame", "pictureframe"]), ("거울", ["mirror"]),
    ("빗", ["comb"]), ("가위", ["scissors"]), ("집게", ["clip", "tongs", "clamp", "peg", "clothespin"]), ("옷걸이", ["hanger"]),
    ("단풍잎", ["leaf", "mapleleaf"]), ("붓", ["brush", "paintbrush"]), ("책", ["book"]), ("공책", ["notebook"]),
    ("봉투", ["envelope", "bag"]), ("리모컨", ["remote", "controller"]), ("시계", ["clock", "watch"]), ("나침반", ["compass"]),
    ("밥그릇", ["bowl", "ricebowl"]), ("장독", ["jar", "crock", "pot"]), ("바가지", ["gourd", "scoop", "dipper", "bowl"]),
    ("뚝배기", ["pot", "bowl"]), ("절구", ["mortar"]), ("삽", ["shovel", "spade"]), ("갈퀴", ["rake"]),
    ("물뿌리개", ["wateringcan", "sprinkler"]), ("주판", ["abacus"]), ("골무", ["thimble"]), ("바늘", ["needle"]),
    ("땅콩", ["peanut"]), ("옥수수", ["corn", "maize", "cob"]), ("당근", ["carrot"]), ("양파", ["onion"]), ("배추", ["cabbage"]),
    ("사과", ["apple"]), ("귤", ["tangerine", "mandarin"]), ("레몬", ["lemon"]), ("만두", ["dumpling"]), ("빵", ["bread", "bun", "loaf"]),
    ("트로피", ["trophy"]), ("왕관", ["crown"]), ("반지", ["ring"]), ("목걸이", ["necklace"]), ("텐트", ["tent"]),
    ("우체통", ["mailbox", "postbox"]), ("계단", ["stairs", "staircase", "steps"]), ("울타리", ["fence"]), ("문", ["door"]),
    ("지팡이", ["cane", "stick", "staff"]),
]
P_FRAMES = [
    lambda x: f"{J(x, '이')} 보여요", lambda x: f"제 앞에 {J(x, '이')} 하나 있어요", lambda x: f"{J(x, '이')} 가슴께에 놓인 것 같아요",
    lambda x: f"잘 보면 {J(x, '이에요')}", lambda x: f"{x}처럼 생긴 게 있어요", lambda x: f"{J(x, '이')} 둥둥 떠 있어요",
    lambda x: f"{x} 하나가 보이는데요", lambda x: f"아무래도 {x} 같아요", lambda x: f"{J(x, '이')} 거기 있어요",
    lambda x: f"{J(x, '이')} 조용히 있어요", lambda x: f"머릿속에 {J(x, '이')} 있어요", lambda x: f"{J(x, '이')} 딱 그려져요",
    lambda x: f"그건 {J(x, '이에요')}", lambda x: f"{J(x, '이')} 한가운데 있어요",
]
SIMILE_NOUNS = [w for w, _ in P_WORDS[:20]]
SIM_PRED = {"VA": ["무거워요", "차가워요", "뜨거워요", "날카로워요", "가벼워요", "따가워요"],
            "XR": ["단단해요", "묵직해요", "딱딱해요", "싸늘해요", "답답해요", "뻣뻣해요", "축축해요", "푹신해요"],
            "VV": ["짓눌러요", "조여 와요", "막혀요", "흔들려요", "떨려요", "가라앉아요"],
            "MAG": ["꽉 막혀요", "콕콕 찔러요", "쿡쿡 쑤셔요", "꾹 눌러요", "착 가라앉아요", "꽁꽁 묶여요"]}
SIM_FRAMES = [lambda x, p: f"{x}처럼 {p}", lambda x, p: f"{x}같이 {p}", lambda x, p: f"꼭 {x}처럼 {p}", lambda x, p: f"마치 {x}처럼 {p}",
              lambda x, p: f"가슴이 {x}처럼 {p}", lambda x, p: f"속이 {x}같이 {p}", lambda x, p: f"어깨가 {x}처럼 {p}",
              lambda x, p: f"그게 {x}처럼 {p}", lambda x, p: f"몸이 {x}같이 {p}", lambda x, p: f"등이 {x}처럼 {p}"]
SHAPE_FRAMES = [lambda x: f"{J(x, '이')} 보여요", lambda x: f"제 앞에 {J(x, '이')} 있어요", lambda x: f"잘 보면 {J(x, '이에요')}",
                lambda x: f"{x}처럼 생긴 게 있어요", lambda x: f"{x} 하나가 보이는데요", lambda x: f"아무래도 {x} 같아요",
                lambda x: f"{J(x, '이')} 웅크린 모습이에요", lambda x: f"그건 {J(x, '이에요')}", lambda x: f"{J(x, '이')} 한가운데 있어요",
                lambda x: f"머릿속에 {J(x, '이')} 있어요", lambda x: f"{x} 비슷한 게 있어요"]
PERSON_WORDS = ["어린애", "아줌마", "할머니", "청년", "여자", "남자아이", "꼬맹이", "사람", "아기", "누나",
                "손가락", "심장", "눈알", "얼굴", "입술", "무릎", "해골", "뇌", "혀", "발가락"]
ANIMAL_WORDS = ["비둘기", "까마귀", "고양이", "강아지", "생쥐", "도롱뇽", "올빼미", "개미", "벌", "잠자리",
                "메기", "가오리", "문어", "늑대", "여우", "토끼", "사슴", "코알라", "족제비", "두루미"]
MIST_WORDS = ["안개", "연기", "구름", "불꽃", "불덩이", "김", "수증기", "물보라", "먹구름", "횃불", "촛불", "모닥불", "불길",
              "그림자", "빛", "햇빛", "번갯불", "무지개", "노을", "아지랑이"]
COLORS = ["청록색", "분홍색", "황토색", "금색", "은색", "베이지색", "자주색", "올리브색", "카키색", "주황색"]
ATTRS = ["축축해요", "따가워요", "뻑뻑해요", "얼얼해요", "시려요", "화끈거려요", "뻐근해요", "아릿해요", "멍해요", "어지러워요"]
NONE_FRAMES = [lambda c, a: J(c, "이에요"), lambda c, a: f"{c}이 돌고 {a}" if batchim(c) else f"{c}가 돌고 {a}",
               lambda c, a: f"그저 {a}", lambda c, a: f"딱히 모양은 없고 {a}", lambda c, a: f"은은하게 {J(c, '이에요')}",
               lambda c, a: f"자꾸 {a}", lambda c, a: f"{c} 느낌이 나요", lambda c, a: f"전체가 {J(c, '이에요')}",
               lambda c, a: f"조금 {a}", lambda c, a: f"그냥 계속 {a}", lambda c, a: f"색깔만 {J(c, '이에요')}"]
WORRY_OBJ = ["프린터", "모니터", "성적표", "면접 서류", "카메라", "노트", "택배", "통장", "자동차 열쇠", "현관 비밀번호",
             "휴대폰 요금", "학자금 대출", "냉장고", "빨래", "보고서", "청첩장", "영수증", "계약서", "운전면허", "졸업 작품"]
WORRY_FRAMES = [lambda o: f"{o} 때문에 요즘 신경이 쓰여요", lambda o: f"{J(o, '을')} 아직 못 챙겨서 걱정이에요",
                lambda o: f"내일 {J(o, '을')} 꼭 처리해야 해요", lambda o: f"{o} 문제가 제일 급해요",
                lambda o: f"{J(o, '이')} 말썽이라 답답해요", lambda o: f"{o} 생각에 잠이 안 와요",
                lambda o: f"{J(o, '을')} 잃어버린 것 같아 불안해요", lambda o: f"자꾸 {o} 쪽 일이 꼬여요",
                lambda o: f"{o} 앞에서 한숨만 나와요", lambda o: f"{J(o, '이')} 계속 마음에 걸려요",
                lambda o: f"{o} 일로 가족과 다퉜어요"]
PER = {"NEG": 50, "PAST": 50, "OTHER": 50, "HYPO": 50, "PERSON": 50, "ANIMAL": 50, "MIST": 50, "NONE": 50, "WORRY": 50}


def blocks(group, frames, words, mk_lines, n, seen):
    out = []
    combos = list(itertools.product(range(len(frames)), range(len(words))))
    order = sorted(combos, key=lambda fw: (fw[1] * 7 + fw[0] * 3) % len(combos))
    for f, w in order:
        lines = mk_lines(frames[f], words[w], len(out))
        key = "\n".join(lines)
        if key in seen:
            continue
        seen.add(key)
        out.append({"group": group, "frame": f, "word": words[w] if isinstance(words[w], str) else list(words[w]),
                    "lines": lines, "expect": "none", "expectKo": None, "enOk": []})
        if len(out) >= n:
            break
    return out


def main():
    prev = json.loads((HERE.parent / "run-g82-llm-shape-eval2" / "cases.json").read_text(encoding="utf-8"))
    seen = {"\n".join(c["lines"]) for c in prev["cases"]}                  # 2차 세트와 같은 확정 텍스트는 만들지 않음
    cases = []
    for n, (w, ok) in enumerate(P_WORDS):
        lines = [WORRY_PLAIN[n % len(WORRY_PLAIN)], FEEL[n % len(FEEL)], P_FRAMES[n % len(P_FRAMES)](w)]
        seen.add("\n".join(lines))
        cases.append({"group": "P", "frame": n % len(P_FRAMES), "word": w, "lines": lines, "expect": "fill",
                      "expectKo": w, "enOk": ok})

    def three(frame, w, k):
        return [WORRY_PLAIN[k % len(WORRY_PLAIN)], FEEL[(k * 3) % len(FEEL)], frame(w)]

    for pos, preds in SIM_PRED.items():                                     # 속성 비유: 서술어 품사마다 50
        words = [(x, p) for x in SIMILE_NOUNS for p in preds]
        got = blocks("SIMILE", [lambda xp, fr=fr: fr(*xp) for fr in SIM_FRAMES], words, three, 50, seen)
        for c in got:
            c["predicatePos"] = pos
        cases += got
    cases += blocks("NEG", NEG, SIMILE_NOUNS + [w for w, _ in P_WORDS[20:30]], three, PER["NEG"], seen)
    cases += blocks("PAST", PAST, [w for w, _ in P_WORDS[10:30]], three, PER["PAST"], seen)
    cases += blocks("OTHER", OTHER, [w for w, _ in P_WORDS[20:40]], three, PER["OTHER"], seen)
    cases += blocks("HYPO", HYPO, [w for w, _ in P_WORDS[30:50]], three, PER["HYPO"], seen)
    cases += blocks("PERSON", SHAPE_FRAMES, PERSON_WORDS, three, PER["PERSON"], seen)
    cases += blocks("ANIMAL", SHAPE_FRAMES, ANIMAL_WORDS, three, PER["ANIMAL"], seen)
    cases += blocks("MIST", SHAPE_FRAMES, MIST_WORDS, three, PER["MIST"], seen)
    cn = [(c, a) for c in COLORS for a in ATTRS]
    cases += blocks("NONE", [lambda ca, fr=fr: fr(*ca) for fr in NONE_FRAMES], cn, three, PER["NONE"], seen)
    nf = [(COLORS[k % len(COLORS)], ATTRS[(k * 3) % len(ATTRS)]) for k in range(len(WORRY_OBJ))]
    cases += blocks("WORRY", WORRY_FRAMES, WORRY_OBJ,
                    lambda frame, o, k: [frame(o), FEEL[k % len(FEEL)], NONE_FRAMES[k % len(NONE_FRAMES)](*nf[k % len(nf)])],
                    PER["WORRY"], seen)
    for i, c in enumerate(cases):
        c["id"] = f"{c['group']}{i:04d}"
    groups = list(dict.fromkeys(c["group"] for c in cases))
    counts = {g: sum(1 for c in cases if c["group"] == g) for g in groups}
    frames = {g: len({c["frame"] for c in cases if c["group"] == g}) for g in groups}
    simpos = {p: sum(1 for c in cases if c.get("predicatePos") == p) for p in SIM_PRED}
    out = {"what": "G82 eval3 fixed synthetic case set (written before the run; do not edit after results)",
           "built": "build_set3.py", "groupCounts": counts, "framesPerGroup": frames, "similePredicatePos": simpos,
           "cases": [{k: c[k] for k in ("id", "group", "frame", "word", "lines", "expect", "expectKo", "enOk")
                      } | ({"predicatePos": c["predicatePos"]} if "predicatePos" in c else {}) for c in cases]}
    (HERE / "cases.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(counts, frames, simpos)


if __name__ == "__main__":
    main()
