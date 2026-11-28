"""G82 2차 평가 문장 세트 만들기(합성 대사만, 참여자 자료 아님). 실행 전에 cases.json으로 고정하고, 결과를 본 뒤 고치지 않는다.

문장 하나 = 정적 면담의 답 세 줄: [찾기 단계(신경 쓰는 일), 머물기 단계(느낌), 구체화 단계(모습)]. 확정 텍스트는 고치지 않으므로
단계 표지(llm_shape.line_stages)를 얻는다. 첫 단계(run-g82-llm-shape-offline)의 45문장과 낱말·말투를 겹치지 않게 했다.

갈래
  P   사전 밖 형태(채워야 함). 낱말마다 허용 번역 목록(enOk)을 실행 전에 적는다. 목록 밖의 넓은 말은 '넓음'으로 따로 센다(채움에 안 넣음)
  NEG 부정 · PAST 과거 · OTHER 타인의 말 · HYPO 가정 · SIMILE 속성 비유 · PERSON 사람·몸 · ANIMAL 동물 · MIST 안개·불꽃류
  NONE 형태 없음 · WORRY 걱정 이야기 속 사물(찾기 단계 줄에만 사물, 모습 줄에는 형태 없음)
차단 갈래는 틀(템플릿) × 낱말 목록으로 찍는다. 갈래마다 틀 10개 이상, 100문장.

실행: python build_set.py  → cases.json(덮어씀. 고정한 뒤에는 다시 돌리지 않는다)
고정 전 규칙만 본 점검(--probe, LLM 없음)에서 바꾼 것 하나: '종'은 조사 '이'와 붙으면 '종이'(규칙 사전의 종이 = paper)가 되어
사전 밖 낱말이 아니었다 → '망원경'으로 바꿈(P·차단 낱말 둘 다). 그 밖에는 고치지 않았다.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PER_GROUP = 100


def batchim(w: str) -> bool:
    c = w[-1]
    return 0xAC00 <= ord(c) <= 0xD7A3 and (ord(c) - 0xAC00) % 28 != 0


def J(w: str, kind: str) -> str:
    """조사·어미 붙이기(받침에 따라)."""
    b = batchim(w)
    table = {"이": ("이", "가"), "은": ("은", "는"), "을": ("을", "를"), "이에요": ("이에요", "예요"),
             "이라고": ("이라고", "라고"), "이었": ("이었", "였"), "이면": ("이면", "면"), "이래요": ("이래요", "래요"),
             "일": ("일", "일"), "인": ("인", "인"), "이길": ("이길", "길"), "이라면": ("이라면", "라면"),
             "이었으면": ("이었으면", "였으면"), "처럼": ("처럼", "처럼")}
    a, z = table[kind]
    return w + (a if b else z)


# 찾기 단계 줄(사물 없음) · 머물기 단계 줄(느낌)
WORRY_PLAIN = ["요즘 회사 일이 많아서 신경 쓰여요", "다음 달 이사 준비가 마음에 걸려요", "가족 일로 계속 마음이 쓰여요",
               "취업 준비가 제일 신경 쓰여요", "졸업 논문이 잘 안 풀려서 걱정이에요", "친구와 다툰 게 계속 마음에 남아요",
               "건강 검진 결과가 신경 쓰여요", "팀 프로젝트 마감이 다가와서 초조해요", "돈 문제가 요즘 제일 걱정이에요",
               "발표를 앞두고 긴장돼요", "아르바이트 일정이 꼬여서 신경 쓰여요"]
FEEL = ["가슴이 묵직해요", "어깨가 뻐근해요", "배 쪽이 싸해요", "목 아래가 무거워요", "명치가 꽉 막힌 느낌이에요",
        "등이 굳어 있어요", "머리가 지끈거려요", "손끝이 차가워요", "가슴 한쪽이 저릿해요", "속이 더부룩해요"]

# ── P: 사전 밖 형태(낱말, 허용 번역 — 실행 전에 고정) ───────────────────────────
P_WORDS = [
    ("주전자", ["kettle", "teapot"]), ("우산", ["umbrella"]), ("열쇠", ["key"]), ("국자", ["ladle"]),
    ("냄비", ["pot", "saucepan"]), ("깔때기", ["funnel"]), ("주사위", ["die", "dice"]), ("도토리", ["acorn"]),
    ("밤송이", ["burr", "chestnut"]), ("호두", ["walnut"]), ("감자", ["potato"]), ("고구마", ["sweetpotato", "yam", "potato"]),
    ("수박", ["watermelon"]), ("전구", ["bulb", "lightbulb"]), ("바구니", ["basket"]), ("빗자루", ["broom"]),
    ("지우개", ["eraser"]), ("연필", ["pencil"]), ("숟가락", ["spoon"]), ("장갑", ["glove", "gloves", "mitten"]),
    ("신발", ["shoe", "shoes"]), ("모자", ["hat", "cap"]), ("의자", ["chair"]), ("타이어", ["tire", "tyre"]),
    ("톱니바퀴", ["gear", "cog", "cogwheel"]), ("나사", ["screw", "bolt"]), ("망원경", ["telescope"]), ("북", ["drum"]),
    ("소라", ["conch", "seashell", "shell"]), ("이불", ["blanket", "quilt", "duvet", "comforter"]), ("수건", ["towel"]),
    ("비누", ["soap"]), ("파이프", ["pipe", "tube"]), ("호스", ["hose"]), ("사다리", ["ladder"]),
    ("자물쇠", ["lock", "padlock"]), ("닻", ["anchor"]), ("깃발", ["flag"]), ("팽이", ["top"]),
    ("화분", ["pot", "flowerpot", "planter"]), ("찻잔", ["teacup", "cup"]), ("그물", ["net"]), ("고드름", ["icicle"]),
    ("모래주머니", ["sandbag"]), ("쇠사슬", ["chain"]), ("쌀자루", ["sack", "ricesack"]), ("바윗덩어리", ["boulder", "rock"]),
    ("얼음덩어리", ["ice", "iceblock", "icecube"]),
]
P_FRAMES = [
    lambda x: f"꼭 {x} 같아요",
    lambda x: f"{J(x, '이')} 떠올라요",
    lambda x: f"{x} 하나가 덩그러니 놓여 있어요",
    lambda x: f"음 {J(x, '이')} 보이는 것 같아요",
    lambda x: f"{x} 비슷한 게 있는데 좀 낡았어요",
    lambda x: f"가만히 보면 {x} 모양이에요",
    lambda x: f"{J(x, '을')} 닮았어요",
    lambda x: f"{J(x, '이')} 가슴 앞에 걸려 있어요",
    lambda x: f"{J(x, '이')} 놓여 있는데 꽤 오래된 느낌이에요",
    lambda x: f"{J(x, '이')} 생각나요",
    lambda x: f"{J(x, '이')} 가만히 있어요",
    lambda x: f"딱 {J(x, '이에요')}",
    lambda x: f"그러니까 {J(x, '이')} 하나 있는 거예요",
    lambda x: f"자꾸 {J(x, '이')} 눈앞에 그려져요",
]

# ── 차단 갈래 ────────────────────────────────────────────────────────────────
BLOCK_NOUNS = ["주전자", "우산", "열쇠", "국자", "냄비", "도토리", "호두", "전구", "바구니", "연필", "의자", "타이어",
               "망원경", "이불", "사다리", "닻", "깃발", "화분", "그물", "고드름"]
NEG = [lambda x: f"{J(x, '은')} 아니에요", lambda x: f"{x} 같은 건 없어요", lambda x: f"{J(x, '이')} 아니라 그냥 느낌만 있어요",
       lambda x: f"{x}처럼 생기지는 않았어요", lambda x: f"{J(x, '은')} 전혀 아니고요", lambda x: f"{J(x, '이')} 있는 건 아니에요",
       lambda x: f"{x} 모양은 아니에요", lambda x: f"{J(x, '은')} 안 보여요", lambda x: f"{J(x, '이')} 떠오르지는 않아요",
       lambda x: f"{x} 같지는 않아요", lambda x: f"{J(x, '을')} 떠올린 건 아니에요"]
PAST = [lambda x: f"예전에는 {J(x, '이었')}어요", lambda x: f"처음엔 {x} 같았어요", lambda x: f"어릴 때는 {J(x, '이었')}어요",
        lambda x: f"아까는 {J(x, '이')} 있었어요", lambda x: f"옛날엔 {x}처럼 보였어요", lambda x: f"그때는 {x} 같았는데요",
        lambda x: f"원래는 {J(x, '이었')}어요", lambda x: f"지난번엔 {J(x, '이')} 떠올랐어요", lambda x: f"전에는 {x} 모양이었어요",
        lambda x: f"처음 떠올렸을 땐 {J(x, '이었')}어요", lambda x: f"작년에는 {x} 같은 게 있었어요"]
OTHER = [lambda x: f"친구가 {x} 같대요", lambda x: f"엄마는 그게 {J(x, '이라고')} 했어요", lambda x: f"선생님이 {x} 같다고 하셨어요",
         lambda x: f"남들은 {J(x, '이라고')} 해요", lambda x: f"동생이 {x} 같다고 그랬어요", lambda x: f"다들 {J(x, '이라고')} 하더라고요",
         lambda x: f"누가 {x} 같다고 말했어요", lambda x: f"언니 말로는 {J(x, '이래요')}", lambda x: f"사람들이 {x} 같대요",
         lambda x: f"아빠는 {J(x, '이라고')} 부르셨어요", lambda x: f"룸메이트가 {x} 같다고 하던데요"]
HYPO = [lambda x: f"{J(x, '이면')} 좋겠어요", lambda x: f"아마 {J(x, '일')} 거예요", lambda x: f"{J(x, '일')}지도 몰라요",
        lambda x: f"혹시 {J(x, '일')}까 싶어요", lambda x: f"만약 {J(x, '이라면')} 덜 무서울 것 같아요",
        lambda x: f"{J(x, '이었으면')} 해요", lambda x: f"{x} 같은 게 있으면 좋겠어요", lambda x: f"{J(x, '이면')} 어떨까 싶어요",
        lambda x: f"{J(x, '을')} 떠올리고 싶어요", lambda x: f"{J(x, '이길')} 바라요", lambda x: f"아마도 {x} 같은 거겠죠"]
SIMILE_PRED = ["무거워요", "단단해요", "차가워요", "답답해요", "꽉 막혀요", "묵직해요", "짓눌려요", "거칠거칠해요", "싸늘해요",
               "조여요", "딱딱해요"]
SIMILE = [lambda x, p=p: f"{x}처럼 {p}" for p in SIMILE_PRED[:6]] + \
         [lambda x, p=p: f"{x}같이 {p}" for p in SIMILE_PRED[6:]]
SHAPE_FRAMES = [lambda x: f"{x} 같은 게 있어요", lambda x: f"{x}처럼 생겼어요", lambda x: J(x, "이에요"),
                lambda x: f"작은 {x} 모양이에요", lambda x: f"{J(x, '이')} 웅크리고 있어요", lambda x: f"{x} 하나가 보여요",
                lambda x: f"꼭 {x} 같아요", lambda x: f"{J(x, '이')} 떠올라요", lambda x: f"{x} 모습이에요",
                lambda x: f"{J(x, '이')} 서 있어요", lambda x: f"{x} 같은 거예요"]
PERSON_WORDS = ["아이", "남자", "할아버지", "아기", "소년", "사람", "노인", "여자아이", "손", "심장", "눈", "얼굴", "주먹",
                "팔", "다리", "뼈", "머리", "입", "이빨", "발"]
ANIMAL_WORDS = ["참새", "다람쥐", "고양이", "강아지", "뱀", "개구리", "물고기", "새", "거북이", "토끼", "나비", "벌레",
                "애벌레", "두더지", "까치", "고슴도치", "오소리", "미어캣", "앵무새", "비버"]
MIST_WORDS = ["안개", "연기", "구름", "불꽃", "불", "수증기", "아지랑이", "물안개", "먹구름", "횃불", "촛불", "모닥불", "불길",
              "그림자", "빛", "햇살", "번개", "무지개", "노을", "입김"]
COLORS = ["쑥색", "회색", "검은색", "잿빛", "남색", "보라색", "연두색", "하늘색", "갈색", "붉은색"]
ATTRS = ["무거워요", "차가워요", "답답해요", "따끔해요", "묵직해요", "울렁거려요", "흐릿해요", "뜨거워요", "저려요", "막막해요"]
NONE_FRAMES = [lambda c, a: J(c, "이에요"), lambda c, a: f"{c}이고 {a}" if batchim(c) else f"{c}고 {a}",
               lambda c, a: f"그냥 {a}", lambda c, a: f"뭔가 {a}", lambda c, a: f"잘 모르겠어요 그냥 {a}",
               lambda c, a: f"{c} 같기도 하고 {a}", lambda c, a: f"흐릿하게 {J(c, '이에요')}",
               lambda c, a: f"색은 {J(c, '이')} 돌아요", lambda c, a: f"조금씩 {a}", lambda c, a: f"계속 {a}",
               lambda c, a: f"딱히 보이는 건 없고 {a}"]
WORRY_OBJ = ["노트북", "휴대폰", "보고서", "서류", "책상", "통장", "시험지", "계약서", "자동차", "냉장고", "지갑", "달력",
             "컴퓨터", "청구서", "이메일", "카드", "원고", "자전거", "세탁기", "현관문"]
WORRY_FRAMES = [lambda o: f"{o} 때문에 걱정이에요", lambda o: f"{J(o, '을')} 잃어버릴까 봐 신경 쓰여요",
                lambda o: f"회사에서 {J(o, '을')} 다시 봐야 해서 불안해요", lambda o: f"{J(o, '이')} 고장 나서 걱정이에요",
                lambda o: f"요즘 {o} 생각만 하면 답답해요", lambda o: f"{o} 문제로 계속 신경 쓰여요",
                lambda o: f"내일까지 {J(o, '을')} 정리해야 해요", lambda o: f"{o} 앞에 앉으면 마음이 무거워요",
                lambda o: f"{J(o, '이')} 자꾸 마음에 걸려요", lambda o: f"{o} 쪽 일이 제일 급해요",
                lambda o: f"엄마가 준 {J(o, '을')} 망가뜨려서 미안해요"]


def blocks(group: str, frames, words, mk_lines):
    out = []
    combos = list(itertools.product(range(len(frames)), range(len(words))))
    # 틀을 고르게: (틀, 낱말)을 틀 순서로 돌려 가며 고름
    order = sorted(combos, key=lambda fw: (fw[1] * 7 + fw[0] * 3) % len(combos))
    seen = set()
    for f, w in order:
        lines = mk_lines(frames[f], words[w], len(out))
        if "\n".join(lines) in seen:
            continue
        seen.add("\n".join(lines))
        out.append({"group": group, "frame": f, "word": words[w], "lines": lines, "expect": "none",
                    "expectKo": None, "enOk": []})
        if len(out) >= PER_GROUP:
            break
    return out


def main():
    cases = []
    for n, (w, ok) in enumerate(P_WORDS):
        frame = P_FRAMES[n % len(P_FRAMES)]
        cases.append({"group": "P", "frame": n % len(P_FRAMES), "word": w,
                      "lines": [WORRY_PLAIN[n % len(WORRY_PLAIN)], FEEL[n % len(FEEL)], frame(w)],
                      "expect": "fill", "expectKo": w, "enOk": ok})

    def three(frame, w, k):
        return [WORRY_PLAIN[k % len(WORRY_PLAIN)], FEEL[(k * 3) % len(FEEL)], frame(w)]

    cases += blocks("NEG", NEG, BLOCK_NOUNS, three)
    cases += blocks("PAST", PAST, BLOCK_NOUNS, three)
    cases += blocks("OTHER", OTHER, BLOCK_NOUNS, three)
    cases += blocks("HYPO", HYPO, BLOCK_NOUNS, three)
    cases += blocks("SIMILE", SIMILE, BLOCK_NOUNS, three)
    cases += blocks("PERSON", SHAPE_FRAMES, PERSON_WORDS, three)
    cases += blocks("ANIMAL", SHAPE_FRAMES, ANIMAL_WORDS, three)
    cases += blocks("MIST", SHAPE_FRAMES, MIST_WORDS, three)
    cn = [(c, a) for c in COLORS for a in ATTRS]
    cases += blocks("NONE", [lambda ca, fr=fr: fr(*ca) for fr in NONE_FRAMES], cn, three)
    nf = [(COLORS[k % len(COLORS)], ATTRS[(k * 3) % len(ATTRS)]) for k in range(len(WORRY_OBJ))]
    cases += blocks("WORRY", WORRY_FRAMES, WORRY_OBJ,
                    lambda frame, o, k: [frame(o), FEEL[k % len(FEEL)], NONE_FRAMES[k % len(NONE_FRAMES)](*nf[k % len(nf)])])
    for i, c in enumerate(cases):
        c["id"] = f"{c['group']}{i:04d}"
    frames = {g: len({c["frame"] for c in cases if c["group"] == g}) for g in dict.fromkeys(c["group"] for c in cases)}
    counts = {g: sum(1 for c in cases if c["group"] == g) for g in frames}
    out = {"what": "G82 eval2 fixed synthetic case set (written before the run; do not edit after results)",
           "built": "build_set.py", "lineStages": ["find", "focus", "flesh_out"], "groupCounts": counts,
           "framesPerGroup": frames, "cases": [{k: c[k] for k in ("id", "group", "frame", "word", "lines", "expect",
                                                                 "expectKo", "enOk")} for c in cases]}
    (HERE / "cases.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(counts, frames)


if __name__ == "__main__":
    main()
