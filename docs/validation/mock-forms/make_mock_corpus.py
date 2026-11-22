"""합성 목업 심상 답변 36개 → mock_corpus.json (dev.json과 같은 형식 + tags·expected·live 필드).

모든 문장은 AI 에이전트가 쓴 합성 대사다(참여자 응답 아님, AGENTS.md 6). 사전(shared/lexicon)과 매퍼 코드를 보지 않고 썼다.
dev.json의 문장을 베끼지 않았다. heldout.json은 열지 않았다.

  python docs/validation/mock-forms/make_mock_corpus.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEYS = ("opening", "location", "focus", "fleshout", "probe_size_shape", "probe_color_brightness", "probe_movement")

AROUND = ["around", "around_front", "around_behind", "around_side", "around_below"]
WHITE = {"s": [0.0, 0.15], "l": [0.8, 1.0]}
BLACK = {"l": [0.0, 0.2]}
GRAY = {"s": [0.0, 0.2], "l": [0.3, 0.7]}
RED = {"hue_deg": [345, 15], "s": [0.5, 1.0], "l": [0.3, 0.65]}
YELLOW = {"hue_deg": [40, 70], "s": [0.4, 1.0], "l": [0.35, 0.8]}
ORANGE = {"hue_deg": [15, 45], "s": [0.5, 1.0], "l": [0.35, 0.7]}
BLUE = {"hue_deg": [195, 250], "s": [0.35, 1.0], "l": [0.25, 0.7]}


def g(attr, phrase, slot=None, expect=None, negated=False):
    return {"attr": attr, "phrase": phrase, "slot": slot, "expect": expect, "negated": negated}


def rng(lo, hi):
    return {"range": [lo, hi]}


def eq(v):
    return {"equals": v}


def isin(*v):
    return {"in": list(v)}


def item(id_, style, replies, gold, tags, expected, distractors=(), live=None):
    r = dict(zip(KEYS, [None] * len(KEYS)))
    r.update(replies)
    out = {"id": id_, "style": style, "replies": r, "gold": gold,
           "distractors": [{"phrase": p, "why": w} for p, w in distractors],
           "tags": tags, "expected": expected}
    if live:
        out["live"] = live
    return out


ITEMS = [
    # ── 안개·연기·구름·김 ────────────────────────────────────────────────
    item("M01", "multi_turn", {
        "opening": "회의 끝나고 집에 오는 길이 떠올라요. 머리 쪽이 뿌옇게 흐린 느낌이 먼저 와요.",
        "location": "몸 주변이요. 머리를 둘러싸고 있어요.",
        "focus": "안개가 끼어 있어요.",
        "fleshout": "잿빛 안개가 방을 채울 만큼 넓게 퍼져 있어요. 뒤가 비쳐 보이긴 하는데 흐릿해요.",
        "probe_movement": "천천히 이리저리 떠다녀요.",
    }, [
        g("form", "안개가 끼어 있어요", "form.type", eq("mist")),
        g("color", "잿빛 안개", "material.color", GRAY),
        g("size", "방을 채울 만큼", "layout.size", rng(0.75, 1.0)),
        g("opacity", "뒤가 비쳐 보이긴 하는데 흐릿해요", "material.opacity", rng(0.2, 0.75)),
        g("motion_type", "이리저리 떠다녀요", "motion.type", isin("floating", "drifting")),
        g("motion_speed", "천천히", "motion.speed", rng(0.0, 0.4)),
        g("body_layer", "몸 주변이요", "body.layer", isin(*AROUND)),
        g("body_part", "머리를 둘러싸고", "body.part", eq("head")),
    ], {"form": ["mist"], "color": ["mid"], "size": ["relative", "body"], "texture": ["semi_transparent"],
        "motion": ["floating"], "response": "all", "speech": "보통"},
       "안개 · 잿빛 · 방을 채울 만큼 큼 · 반투명 · 천천히 떠다님 · 머리 주변",
       distractors=[("회의", "떠올린 상황(맥락)")],
       live={"find": ["머리 둘레가 뿌예요."],
             "flesh_out_extra": ["잿빛이에요. 축축한 느낌도 있어요.", "가장자리는 더 옅어요.",
                                 "그냥 천천히 떠다녀요.", "그 정도예요."]}),

    item("M02", "free_narrative", {
        "opening": "음… 친구랑 연락이 끊긴 일이요. 가슴 안쪽에서 검은 연기 같은 게 스멀스멀 피어올라요. 크기는 잘 모르겠고, 아주 진하진 않고 좀 비쳐요.",
        "location": "몸 안이요.",
        "focus": "계속 올라와요.",
        "fleshout": "그게 다예요.",
    }, [
        g("form", "검은 연기 같은 게", "form.type", eq("mist")),
        g("color", "검은 연기", "material.color", BLACK),
        g("size", "크기는 잘 모르겠고", "layout.size", eq(None)),
        g("opacity", "아주 진하진 않고 좀 비쳐요", "material.opacity", rng(0.3, 0.85)),
        g("motion_type", "스멀스멀 피어올라요", "motion.type", isin("rising", "spreading")),
        g("body_part", "가슴 안쪽", "body.part", isin("chest", "heart")),
        g("body_layer", "몸 안이요", "body.layer", eq("inner")),
    ], {"form": ["mist"], "color": ["basic"], "size": ["body", "unknown"], "texture": ["semi_transparent"],
        "motion": ["rising"], "response": "dont_know_part", "speech": "머뭇거림·한 번에 길게"},
       "연기 · 검정 · 크기 모름 · 조금 비침 · 피어오름 · 가슴 안",
       distractors=[("친구랑 연락이 끊긴 일", "떠올린 상황(맥락)")]),

    item("M03", "multi_turn", {
        "opening": "출근길이요. 뭔가 몽글몽글한 게 있어요.",
        "location": "주변이요.",
        "focus": "구름이에요.",
        "fleshout": "하얀 구름이에요.",
        "probe_size_shape": "제 머리보다 조금 커요.",
        "probe_movement": "둥둥 떠 있으면서 조금씩 커졌다 작아졌다 해요.",
    }, [
        g("form", "구름이에요", "form.type", isin("mist")),
        g("color", "하얀 구름", "material.color", WHITE),
        g("size", "제 머리보다 조금 커요", "layout.size", rng(0.35, 0.7)),
        g("motion_type", "둥둥 떠 있으면서", "motion.type", isin("floating", "drifting")),
        g("other", "커졌다 작아졌다 해요"),
        g("body_layer", "주변이요", "body.layer", isin(*AROUND)),
    ], {"form": ["mist"], "color": ["basic"], "size": ["relative"], "texture": [],
        "motion": ["floating", "grow_shrink"], "response": "partial", "speech": "짧게 한마디"},
       "구름(평서 명사) · 하양 · 머리보다 조금 큼 · 떠 있음 · 커졌다 작아졌다"),

    item("M04", "multi_turn", {
        "opening": "저녁에 혼자 라면 끓이던 때요. 목 언저리가 따뜻해요.",
        "location": "몸 표면이요. 목 앞쪽에요.",
        "focus": "김 같은 게 올라와요.",
        "fleshout": "뜨거운 물에서 나는 김처럼 위로 솔솔 올라가요. 색은 없어요. 거의 투명해서 잘 안 보일 정도예요.",
        "probe_size_shape": "손바닥 두 개 정도요.",
    }, [
        g("form", "김 같은 게", "form.type", eq("mist")),
        g("color", "색은 없어요", "material.color", eq(None)),
        g("opacity", "거의 투명해서", "material.opacity", rng(0.0, 0.3)),
        g("motion_type", "위로 솔솔 올라가요", "motion.type", isin("rising")),
        g("size", "손바닥 두 개 정도요", "layout.size", rng(0.25, 0.6)),
        g("body_part", "목 앞쪽", "body.part", isin("throat", "throat_neck")),
        g("body_layer", "몸 표면이요", "body.layer", eq("surface")),
        g("temperature", "따뜻해요"),
    ], {"form": ["mist"], "color": ["none"], "size": ["numeric_ref", "body"], "texture": ["almost_transparent"],
        "motion": ["rising"], "response": "partial", "speech": "보통"},
       "김 · 색 없음 · 거의 투명 · 손바닥 두 개 · 위로 올라감 · 목 앞 표면",
       distractors=[("라면", "떠올린 상황의 사물(맥락)")]),

    # ── 덩어리·뭉치 ─────────────────────────────────────────────────────
    item("M05", "multi_turn", {
        "opening": "발표 전날 밤이 떠올라요. 배 속에 뭔가 묵직한 게 있어요.",
        "location": "몸 안이요, 명치 아래쯤.",
        "focus": "덩어리가 하나 있어요.",
        "fleshout": "딱딱한 덩어리예요. 남색이고, 주먹만 해요. 겉은 조금 거칠어요.",
        "probe_movement": "움직이진 않아요. 그냥 박혀 있어요.",
    }, [
        g("form", "덩어리가 하나", "form.type", eq("blob")),
        g("hardness", "딱딱한 덩어리"),
        g("color", "남색", "material.color", {"hue_deg": [210, 250], "s": [0.3, 1.0], "l": [0.1, 0.4]}),
        g("size", "주먹만 해요", "layout.size", rng(0.05, 0.5)),
        g("texture_roughness", "겉은 조금 거칠어요", "material.roughness", rng(0.55, 0.85)),
        g("motion_type", "움직이진 않아요", "motion.type", isin("still")),
        g("body_part", "명치 아래", "body.part", isin("solar_plexus", "belly")),
        g("body_layer", "몸 안이요", "body.layer", eq("inner")),
        g("weight", "묵직한"),
    ], {"form": ["lump"], "color": ["mid"], "size": ["numeric_ref", "body"], "texture": ["hard", "rough"],
        "motion": ["still"], "response": "all", "speech": "보통"},
       "덩어리 · 남색 · 주먹만 · 딱딱·거칠 · 안 움직임 · 명치 아래",
       live={"find": ["배 한가운데가 묵직해요."],
             "flesh_out_extra": ["돌처럼 단단해요.", "겉이 좀 까슬까슬해요.", "계속 그 자리에 있어요.", "더는 없어요."]}),

    item("M06", "multi_turn", {
        "opening": "해야 할 일이 잔뜩 쌓였던 주요. 머릿속이 복잡해요.",
        "location": "몸 안, 머리 안쪽이요.",
        "focus": "실이 엉켜 있는 것 같아요.",
        "fleshout": "털실 뭉치처럼 실이 마구 엉켜서 동그랗게 뭉쳐 있어요. 빨간 실이랑 파란 실이 섞여 있어요.",
        "probe_size_shape": "테니스공 정도요.",
        "probe_movement": "가끔 살짝 꿈틀거려요.",
    }, [
        g("lines", "실이 마구 엉켜서"),
        g("form", "동그랗게 뭉쳐 있어요", "form.type", isin("blob")),
        g("color", "빨간 실", "material.color", RED),
        g("color2", "파란 실"),
        g("size", "테니스공 정도요", "layout.size", rng(0.1, 0.5)),
        g("motion_type", "꿈틀거려요", "motion.type", isin("wriggling")),
        g("body_part", "머리 안쪽", "body.part", eq("head")),
        g("body_layer", "몸 안", "body.layer", eq("inner")),
    ], {"form": ["lump", "lines"], "color": ["mixed"], "size": ["numeric_ref"], "texture": [],
        "motion": ["wriggling"], "response": "partial", "speech": "비유"},
       "엉킨 실 뭉치 · 빨강+파랑 섞임 · 테니스공 · 꿈틀"),

    item("M07", "multi_turn", {
        "opening": "동생이랑 오랜만에 통화했던 거요. 배가 간질간질한 느낌이에요.",
        "location": "몸 안에요. 아랫배요.",
        "focus": "말랑한 뭉치 같은 게 있어요.",
        "fleshout": "살구색 뭉치예요. 찰흙처럼 말랑말랑하고, 숨 쉬듯이 부풀었다 줄었다 해요.",
        "probe_size_shape": "귤 하나 정도요.",
    }, [
        g("form", "말랑한 뭉치", "form.type", eq("blob")),
        g("color", "살구색", "material.color", {"hue_deg": [12, 40], "s": [0.3, 0.95], "l": [0.55, 0.88]}),
        g("softness", "찰흙처럼 말랑말랑하고"),
        g("motion_type", "부풀었다 줄었다 해요", "motion.type", None),
        g("size", "귤 하나 정도요", "layout.size", rng(0.05, 0.45)),
        g("body_part", "아랫배", "body.part", isin("lower_belly", "belly")),
        g("body_layer", "몸 안에요", "body.layer", eq("inner")),
    ], {"form": ["lump"], "color": ["mid"], "size": ["numeric_ref", "body"], "texture": ["soft"],
        "motion": ["pulsing", "grow_shrink"], "response": "all", "speech": "비유"},
       "뭉치 · 살구색 · 말랑 · 귤 크기 · 숨 쉬듯 부풀었다 줄었다 · 아랫배"),

    # ── 껍질·막·껍데기 ──────────────────────────────────────────────────
    item("M08", "multi_turn", {
        "opening": "회사에서 혼났던 일이요. 가슴 앞이 굳는 느낌이에요.",
        "location": "몸 표면이요. 가슴 앞을 덮고 있어요.",
        "focus": "딱딱한 껍질 같아요.",
        "fleshout": "나무껍질처럼 거칠고 딱딱한 껍질이 가슴을 덮고 있어요. 갈색이에요.",
        "probe_size_shape": "가슴을 다 덮을 만큼이요.",
        "probe_movement": "아니요, 안 움직여요.",
    }, [
        g("form", "딱딱한 껍질", "form.type", eq("shell")),
        g("texture_roughness", "나무껍질처럼 거칠고", "material.roughness", rng(0.6, 1.0)),
        g("color", "갈색이에요", "material.color", {"hue_deg": [10, 45], "s": [0.2, 0.8], "l": [0.12, 0.45]}),
        g("size", "가슴을 다 덮을 만큼", "layout.size", rng(0.35, 0.8)),
        g("motion_type", "안 움직여요", "motion.type", isin("still")),
        g("body_part", "가슴 앞", "body.part", eq("chest")),
        g("body_layer", "몸 표면이요", "body.layer", eq("surface")),
    ], {"form": ["shell"], "color": ["basic"], "size": ["relative", "body"], "texture": ["rough", "hard"],
        "motion": ["still"], "response": "all", "speech": "보통"},
       "껍질 · 갈색 · 거칠·딱딱 · 가슴을 덮을 만큼 · 안 움직임 · 가슴 표면",
       live={"find": ["가슴 앞이 뻣뻣해요."],
             "flesh_out_extra": ["나무껍질 같아요.", "꽤 두꺼워요.", "그대로 있어요.", "더 떠오르는 건 없어요."]}),

    item("M09", "multi_turn", {
        "opening": "새 동네로 이사 온 첫날이 생각나요. 몸 둘레에 뭔가 얇은 게 있어요.",
        "location": "몸 주변이요, 저를 빙 둘러싸고 있어요.",
        "focus": "막이요. 얇은 막.",
        "fleshout": "비눗방울 막처럼 얇은데 연두색 빛이 살짝 돌아요. 반쯤 투명해서 바깥이 흐리게 보여요.",
        "probe_size_shape": "저를 통째로 감쌀 만큼 커요.",
        "probe_movement": "살짝살짝 일렁여요.",
    }, [
        g("form", "얇은 막", "form.type", eq("shell")),
        g("color", "연두색", "material.color", {"hue_deg": [65, 110], "s": [0.3, 1.0], "l": [0.4, 0.82]}),
        g("opacity", "반쯤 투명해서", "material.opacity", rng(0.25, 0.7)),
        g("size", "저를 통째로 감쌀 만큼 커요", "layout.size", rng(0.75, 1.0)),
        g("motion_type", "일렁여요", "motion.type", isin("rippling", "swaying")),
        g("body_layer", "몸 주변이요", "body.layer", isin(*AROUND)),
    ], {"form": ["shell", "sheet"], "color": ["mid"], "size": ["relative"], "texture": ["semi_transparent"],
        "motion": ["rippling"], "response": "all", "speech": "비유"},
       "막 · 연두 · 반투명 · 몸 전체를 감쌀 만큼 · 일렁임 · 몸 주변"),

    item("M10", "multi_turn", {
        "opening": "시험 결과 기다리던 때요.",
        "location": "음… 몸 안인 것 같아요.",
        "focus": "속이 빈 껍데기가 있어요.",
        "fleshout": "달걀 껍데기 같아요. 하얗고 얇은데 군데군데 금이 가 있어요. 금 간 데로만 빛이 비쳐요. 안은 비어 있고요.",
        "probe_size_shape": "달걀보다 조금 커요.",
        "probe_movement": "조금씩 떨려요.",
    }, [
        g("form", "껍데기", "form.type", eq("shell")),
        g("color", "하얗고", "material.color", WHITE),
        g("erosion", "군데군데 금이 가 있어요", "material.erosion", rng(0.15, 0.7)),
        g("opacity", "금 간 데로만 빛이 비쳐요", "material.opacity", None),
        g("hollow", "안은 비어 있고요"),
        g("size", "달걀보다 조금 커요", "layout.size", rng(0.05, 0.45)),
        g("motion_type", "조금씩 떨려요", "motion.type", isin("trembling", "vibrating")),
        g("body_layer", "몸 안인 것 같아요", "body.layer", eq("inner")),
    ], {"form": ["shell", "hole"], "color": ["basic"], "size": ["numeric_ref"], "texture": ["partial_transparent"],
        "motion": ["trembling"], "response": "partial", "speech": "머뭇거림"},
       "달걀 껍데기 · 하양 · 금 감 · 금 간 곳만 비침 · 속 빔 · 달걀보다 조금 큼 · 떨림"),

    # ── 조각·파편·부스러기 ──────────────────────────────────────────────
    item("M11", "multi_turn", {
        "opening": "계획이 다 틀어졌던 날이요. 가슴 쪽에 뭔가 부서진 게 있어요.",
        "location": "몸 안이요.",
        "focus": "조각들이 흩어져 있어요.",
        "fleshout": "파란 조각 여러 개가 여기저기 흩어져 있어요. 하나하나가 엄지손톱만 하고 모서리가 날카로워요.",
        "probe_movement": "느릿느릿 맴돌아요.",
    }, [
        g("form", "조각들이 흩어져", "form.type", eq("fragments")),
        g("color", "파란 조각", "material.color", BLUE),
        g("size", "엄지손톱만 하고", "layout.size", rng(0.0, 0.35)),
        g("shape", "모서리가 날카로워요"),
        g("motion_type", "맴돌아요", "motion.type", isin("circling", "rotating", "drifting")),
        g("motion_speed", "느릿느릿", "motion.speed", rng(0.0, 0.4)),
        g("body_part", "가슴 쪽", "body.part", eq("chest")),
        g("body_layer", "몸 안이요", "body.layer", eq("inner")),
    ], {"form": ["fragments", "pointed"], "color": ["basic"], "size": ["numeric_ref", "body"], "texture": [],
        "motion": ["floating"], "response": "partial", "speech": "보통"},
       "조각 · 파랑 · 엄지손톱만 · 모서리 날카로움 · 느리게 맴돎 · 가슴 안"),

    item("M12", "multi_turn", {
        "opening": "오래된 사진을 정리하던 저녁이요. 눈앞에 반짝이는 게 보여요.",
        "location": "몸 앞쪽, 주변이요.",
        "focus": "유리 파편 같은 게 떠 있어요.",
        "fleshout": "깨진 유리 파편들이 공중에 떠 있는데, 거의 투명하고 빛을 받으면 반짝반짝해요. 팔 뻗으면 닿을 거리쯤에 있어요.",
        "probe_size_shape": "다 모으면 베개만 해요.",
        "probe_movement": "거의 안 움직이고 떠 있기만 해요.",
    }, [
        g("form", "유리 파편", "form.type", eq("fragments")),
        g("opacity", "거의 투명하고", "material.opacity", rng(0.0, 0.3)),
        g("brightness", "빛을 받으면 반짝반짝해요", "material.brightness", rng(0.55, 1.0)),
        g("distance", "팔 뻗으면 닿을 거리쯤에", "layout.distance", rng(0.05, 0.3)),
        g("size", "다 모으면 베개만 해요", "layout.size", rng(0.4, 0.75)),
        g("motion_type", "거의 안 움직이고 떠 있기만 해요", "motion.type", isin("still", "floating")),
        g("body_layer", "몸 앞쪽, 주변이요", "body.layer", isin("around_front", "around")),
    ], {"form": ["fragments"], "color": ["none"], "size": ["relative", "distance"], "texture": ["almost_transparent", "sparkle"],
        "motion": ["still", "floating"], "response": "all", "speech": "길게 풀어서"},
       "유리 파편 · 거의 투명 · 반짝 · 베개만 · 팔 길이 앞 · 떠 있음",
       distractors=[("오래된 사진", "떠올린 상황의 사물(맥락)")],
       live={"find": ["반짝이는 게 여러 개예요."],
             "flesh_out_extra": ["유리처럼 투명해요.", "끝이 뾰족뾰족해요.", "가만히 떠 있어요.", "그게 다예요."]}),

    item("M13", "multi_turn", {
        "opening": "음, 그냥 평범한 화요일이요. 잘 모르겠는데… 어깨에 뭐가 묻은 것 같아요.",
        "location": "표면이요. 어깨 위요.",
        "focus": "부스러기 같은 게 있어요.",
        "fleshout": "빵가루 같은 회색 부스러기가 어깨에서 조금씩 아래로 떨어져요.",
        "probe_size_shape": "알갱이 하나는 깨알만 해요.",
    }, [
        g("form", "부스러기 같은 게", "form.type", eq("fragments")),
        g("color", "회색 부스러기", "material.color", GRAY),
        g("motion_type", "아래로 떨어져요", "motion.type", isin("sinking", "settling", "scattering", "collapsing")),
        g("size", "깨알만 해요", "layout.size", rng(0.0, 0.2)),
        g("body_part", "어깨 위요", "body.part", eq("shoulder")),
        g("body_layer", "표면이요", "body.layer", eq("surface")),
    ], {"form": ["fragments"], "color": ["basic"], "size": ["numeric_ref", "body"], "texture": [],
        "motion": ["dripping"], "response": "partial", "speech": "머뭇거림"},
       "부스러기 · 회색 · 깨알만 · 아래로 떨어짐 · 어깨 표면"),

    # ── 둥근/네모난/납작한/뾰족한 ───────────────────────────────────────
    item("M14", "multi_turn", {
        "opening": "주말 아침 산책이요. 배 앞쪽이 동글동글한 느낌이에요.",
        "location": "몸 앞에, 주변이요. 한두 걸음 앞에 있어요.",
        "focus": "둥근 게 있어요.",
        "fleshout": "완전히 둥근 공 모양이에요. 주황색이고 표면이 미끄러울 만큼 매끈해요. 은은하게 빛나요.",
        "probe_size_shape": "배구공만 해요.",
        "probe_movement": "제자리에서 천천히 굴러요.",
    }, [
        g("shape", "완전히 둥근 공 모양"),
        g("color", "주황색", "material.color", ORANGE),
        g("texture_roughness", "미끄러울 만큼 매끈해요", "material.roughness", rng(0.0, 0.3)),
        g("brightness", "은은하게 빛나요", "material.brightness", rng(0.5, 0.85)),
        g("size", "배구공만 해요", "layout.size", rng(0.4, 0.75)),
        g("distance", "한두 걸음 앞에", "layout.distance", rng(0.2, 0.55)),
        g("motion_type", "제자리에서 천천히 굴러요", "motion.type", isin("rotating")),
        g("body_layer", "몸 앞에, 주변이요", "body.layer", isin("around_front", "around")),
    ], {"form": ["round"], "color": ["basic"], "size": ["numeric_ref", "distance"], "texture": ["smooth", "glow"],
        "motion": ["rotating"], "response": "all", "speech": "보통"},
       "둥근 공 · 주황 · 매끈 · 은은히 빛남 · 배구공 · 한두 걸음 앞 · 굴러감"),

    item("M15", "multi_turn", {
        "opening": "이사 준비하던 때요. 등이 무거워요.",
        "location": "몸 표면이요, 등에 붙어 있어요.",
        "focus": "네모난 상자 같아요.",
        "fleshout": "까만 네모난 상자예요. 모서리가 각지고 딱딱해요. 신발 상자만 해요.",
        "probe_movement": "움직임은 없어요.",
    }, [
        g("shape", "네모난 상자"),
        g("color", "까만", "material.color", BLACK),
        g("hardness", "모서리가 각지고 딱딱해요"),
        g("size", "신발 상자만 해요", "layout.size", rng(0.25, 0.65)),
        g("motion_type", "움직임은 없어요", "motion.type", isin("still")),
        g("body_part", "등에 붙어", "body.part", isin("back")),
        g("body_layer", "몸 표면이요", "body.layer", eq("surface")),
    ], {"form": ["square"], "color": ["basic"], "size": ["numeric_ref", "body"], "texture": ["hard"],
        "motion": ["still"], "response": "partial", "speech": "짧게"},
       "네모난 상자 · 검정 · 딱딱 · 신발 상자만 · 안 움직임 · 등 표면"),

    item("M16", "free_narrative", {
        "opening": "할머니 댁 마당이 떠올라요. 명치 쪽이 눌려요. 강가에 있는 납작한 돌처럼 생긴 게 놓여 있는데, 9 cm쯤이고 회색에 하얀 줄무늬가 섞여 있어요. 차갑고 매끄러워요.",
        "location": "몸 안이요.",
        "focus": "그대로 놓여 있어요.",
        "fleshout": "그거 말고는 없어요.",
    }, [
        g("shape", "납작한 돌처럼"),
        g("size", "9 cm쯤", "layout.size", rng(0.03, 0.4)),
        g("color", "회색에", "material.color", GRAY),
        g("color2", "하얀 줄무늬"),
        g("temperature", "차갑고"),
        g("texture_roughness", "매끄러워요", "material.roughness", rng(0.0, 0.35)),
        g("motion_type", "그대로 놓여 있어요", "motion.type", isin("still")),
        g("body_part", "명치 쪽", "body.part", eq("solar_plexus")),
        g("body_layer", "몸 안이요", "body.layer", eq("inner")),
    ], {"form": ["flat"], "color": ["mixed"], "size": ["numeric_unit", "body"], "texture": ["smooth"],
        "motion": ["still"], "response": "all", "speech": "한 번에 길게"},
       "납작한 돌 · 회색+하얀 줄 · 9 cm · 매끈 · 가만히 · 명치 안",
       distractors=[("할머니 댁 마당", "떠올린 장소(맥락)")]),

    item("M17", "multi_turn", {
        "opening": "동료가 한 말이 계속 걸려요. 목에 뭔가 걸린 것 같아요.",
        "location": "몸 안이요, 목구멍 쪽.",
        "focus": "뾰족한 게 있어요.",
        "fleshout": "가시처럼 끝이 뾰족해요. 빨갛고, 새끼손가락 반만 해요. 가끔 파르르 떨려요.",
    }, [
        g("shape", "끝이 뾰족해요"),
        g("color", "빨갛고", "material.color", RED),
        g("size", "새끼손가락 반만 해요", "layout.size", rng(0.0, 0.3)),
        g("motion_type", "파르르 떨려요", "motion.type", isin("trembling", "vibrating")),
        g("body_part", "목구멍 쪽", "body.part", isin("throat", "throat_neck")),
        g("body_layer", "몸 안이요", "body.layer", eq("inner")),
    ], {"form": ["pointed"], "color": ["basic"], "size": ["numeric_ref", "body"], "texture": [],
        "motion": ["trembling"], "response": "all", "speech": "비유"},
       "뾰족한 가시 · 빨강 · 새끼손가락 반 · 파르르 떨림 · 목 안"),

    # ── 선·실·엉킨 것 ──────────────────────────────────────────────────
    item("M18", "multi_turn", {
        "opening": "음… 뭐라고 해야 할지. 어제 일이요. 손끝이 저릿해요.",
        "location": "몸 표면, 손이요.",
        "focus": "실 같은 게 감겨 있어요.",
        "fleshout": "가느다란 검은 실이 손가락에 여러 번 칭칭 감겨 있어요. 엉켜서 어디가 끝인지 모르겠어요.",
        "probe_size_shape": "실은 머리카락만큼 가늘어요.",
        "probe_movement": "조금씩 조여 와요.",
    }, [
        g("lines", "가느다란 검은 실"),
        g("color", "검은 실", "material.color", BLACK),
        g("width", "머리카락만큼 가늘어요"),
        g("motion_type", "조금씩 조여 와요", "motion.type", None),
        g("body_part", "손가락", "body.part", eq("hand")),
        g("body_layer", "몸 표면", "body.layer", eq("surface")),
    ], {"form": ["lines"], "color": ["basic"], "size": ["width_only", "body"], "texture": [],
        "motion": ["other"], "response": "partial", "speech": "머뭇거림"},
       "엉킨 검은 실 · 머리카락 굵기 · 조여 옴 · 손 표면",
       live={"find": ["손가락이 묶인 느낌이에요."],
             "flesh_out_extra": ["실이 아주 가늘어요.", "엉켜 있어요.", "조금씩 조여요.", "더는 없어요."]}),

    item("M19", "multi_turn", {
        "opening": "새벽에 깼을 때요. 등을 따라서 뭔가 지나가요.",
        "location": "몸 안이요. 척추를 따라서요.",
        "focus": "선이요. 한 줄로 쭉.",
        "fleshout": "가느다란 선 하나가 위에서 아래로 길게 이어져 있어요. 금빛이고 희미하게 빛나요.",
        "probe_size_shape": "길이는 40센티쯤이요.",
        "probe_movement": "빛이 아래로 천천히 흘러내려요.",
    }, [
        g("lines", "가느다란 선 하나"),
        g("color", "금빛", "material.color", {"hue_deg": [35, 60], "s": [0.4, 1.0], "l": [0.35, 0.75]}),
        g("brightness", "희미하게 빛나요", "material.brightness", rng(0.4, 0.75)),
        g("size", "길이는 40센티쯤이요", "layout.size", rng(0.3, 0.75)),
        g("motion_type", "아래로 천천히 흘러내려요", "motion.type", None),
        g("motion_speed", "천천히 흘러내려요", "motion.speed", rng(0.0, 0.4)),
        g("body_part", "척추를 따라서요", "body.part", isin("back")),
        g("body_layer", "몸 안이요", "body.layer", eq("inner")),
    ], {"form": ["lines", "light"], "color": ["mid"], "size": ["numeric_unit"], "texture": ["glow"],
        "motion": ["dripping"], "response": "all", "speech": "짧게"},
       "가는 선 · 금빛 · 희미하게 빛남 · 40 cm · 아래로 흘러내림 · 척추 안"),

    # ── 얇은 판·종이·천 ─────────────────────────────────────────────────
    item("M20", "multi_turn", {
        "opening": "제출 마감 직전이요.",
        "location": "주변이요. 눈앞이요.",
        "focus": "종이 한 장이 있어요.",
        "fleshout": "A4 종이 한 장이 눈높이쯤에 떠 있어요. 얇고 하얘요. 가장자리가 살짝 구겨져 있어요.",
        "probe_movement": "살랑살랑 팔랑거려요.",
    }, [
        g("sheet", "종이 한 장"),
        g("size", "A4 종이 한 장", "layout.size", rng(0.25, 0.65)),
        g("color", "하얘요", "material.color", WHITE),
        g("height", "눈높이쯤에", "layout.verticalOffset", rng(0.85, 1.0)),
        g("wrinkle", "가장자리가 살짝 구겨져 있어요"),
        g("motion_type", "팔랑거려요", "motion.type", isin("swaying", "rippling", "floating")),
        g("body_layer", "주변이요", "body.layer", isin(*AROUND)),
    ], {"form": ["sheet"], "color": ["basic"], "size": ["numeric_ref", "height"], "texture": [],
        "motion": ["floating"], "response": "partial", "speech": "짧게"},
       "종이 한 장 · 하양 · A4 · 눈높이 · 팔랑임"),

    item("M21", "multi_turn", {
        "opening": "엄마랑 통화하고 나서요. 어깨가 덮인 느낌이에요.",
        "location": "표면이요. 어깨랑 등을 덮고 있어요.",
        "focus": "천 같아요.",
        "fleshout": "얇은 천이 어깨에 걸쳐서 아래로 흘러내려요. 보라색이랑 남색이 섞여 있고 반투명해요. 손으로 만지면 부드러울 것 같아요.",
        "probe_size_shape": "제 상체를 다 덮을 정도요.",
    }, [
        g("sheet", "얇은 천"),
        g("color", "보라색", "material.color", {"hue_deg": [255, 300], "s": [0.25, 1.0], "l": [0.2, 0.65]}),
        g("color2", "남색이 섞여"),
        g("opacity", "반투명해요", "material.opacity", rng(0.2, 0.7)),
        g("softness", "부드러울 것 같아요"),
        g("motion_type", "아래로 흘러내려요", "motion.type", None),
        g("size", "상체를 다 덮을 정도요", "layout.size", rng(0.5, 0.85)),
        g("body_part", "어깨랑 등", "body.part", isin("shoulder", "back")),
        g("body_layer", "표면이요", "body.layer", eq("surface")),
    ], {"form": ["sheet"], "color": ["mixed", "mid"], "size": ["relative", "body"], "texture": ["semi_transparent", "soft"],
        "motion": ["dripping"], "response": "all", "speech": "길게 풀어서"},
       "얇은 천 · 보라+남색 · 반투명 · 상체를 덮을 만큼 · 흘러내림 · 어깨 표면"),

    # ── 액체·물방울·웅덩이 ──────────────────────────────────────────────
    item("M22", "multi_turn", {
        "opening": "비 오는 날 버스 정류장이요.",
        "location": "몸 안이요. 눈 뒤쪽이요.",
        "focus": "물방울 하나가 맺혀 있어요.",
        "fleshout": "동그란 물방울이에요. 가운데는 맑게 비치는데 가장자리만 뿌예요. 콩알만 해요, 1센티쯤이요.",
        "probe_color_brightness": "색은 딱히 없어요.",
        "probe_movement": "톡 떨어질 듯 말 듯 매달려 있어요.",
    }, [
        g("liquid", "물방울 하나가 맺혀"),
        g("opacity", "가운데는 맑게 비치는데 가장자리만 뿌예요", "material.opacity", None),
        g("size", "콩알만 해요", "layout.size", rng(0.0, 0.2)),
        g("color", "색은 딱히 없어요", "material.color", eq(None)),
        g("motion_type", "떨어질 듯 말 듯 매달려 있어요", "motion.type", None),
        g("body_part", "눈 뒤쪽", "body.part", isin("head", "face")),
        g("body_layer", "몸 안이요", "body.layer", eq("inner")),
    ], {"form": ["liquid", "round"], "color": ["none"], "size": ["numeric_unit", "body"], "texture": ["partial_transparent"],
        "motion": ["still"], "response": "partial", "speech": "짧게"},
       "물방울 · 색 없음 · 가운데만 맑음(부분 투명) · 콩알(1 cm) · 매달려 있음 · 눈 뒤",
       distractors=[("버스 정류장", "떠올린 장소(맥락)")]),

    item("M23", "multi_turn", {
        "opening": "일이 꼬였던 월요일이요. 발이 무거워요.",
        "location": "몸 주변, 발밑이요.",
        "focus": "웅덩이가 있어요.",
        "fleshout": "발밑에 고인 웅덩이 같아요. 탁한 초록색이고 바닥이 안 보여요. 제가 서 있는 자리보다 조금 넓어요.",
        "probe_movement": "표면이 가끔 잔물결처럼 일렁여요.",
    }, [
        g("liquid", "고인 웅덩이"),
        g("color", "탁한 초록색", "material.color", {"hue_deg": [75, 165], "s": [0.08, 0.6], "l": [0.12, 0.45]}),
        g("opacity", "바닥이 안 보여요", "material.opacity", rng(0.7, 1.0)),
        g("height", "발밑에", "layout.verticalOffset", rng(0.0, 0.08)),
        g("size", "서 있는 자리보다 조금 넓어요", "layout.size", rng(0.35, 0.8)),
        g("motion_type", "잔물결처럼 일렁여요", "motion.type", isin("rippling")),
        g("body_layer", "몸 주변", "body.layer", isin("around_below", "around")),
    ], {"form": ["liquid"], "color": ["mid"], "size": ["relative", "height"], "texture": ["dark"],
        "motion": ["rippling"], "response": "all", "speech": "보통"},
       "웅덩이 · 탁한 초록 · 불투명(바닥 안 보임) · 서 있는 자리보다 조금 넓음 · 발밑 · 잔물결"),

    item("M24", "free_narrative", {
        "opening": "피곤했던 금요일 저녁이요. 목에서 가슴으로 뭔가 내려가요. 꿀처럼 진득한 노란 액체가 천천히 흘러내리는데 빛을 받으면 반짝여요. 양은 한 컵쯤이요.",
        "location": "몸 안이요.",
        "focus": "계속 내려가고 있어요.",
        "fleshout": "끈적끈적해요.",
    }, [
        g("liquid", "진득한 노란 액체"),
        g("color", "노란 액체", "material.color", YELLOW),
        g("motion_type", "천천히 흘러내리는데", "motion.type", None),
        g("motion_speed", "천천히", "motion.speed", rng(0.0, 0.4)),
        g("texture_roughness", "빛을 받으면 반짝여요", "material.roughness", rng(0.0, 0.35)),
        g("size", "양은 한 컵쯤이요", "layout.size", rng(0.05, 0.45)),
        g("stickiness", "끈적끈적해요"),
        g("body_part", "목에서 가슴으로", "body.part", isin("chest", "throat", "throat_neck")),
        g("body_layer", "몸 안이요", "body.layer", eq("inner")),
    ], {"form": ["liquid"], "color": ["basic"], "size": ["numeric_ref"], "texture": ["sparkle"],
        "motion": ["dripping"], "response": "all", "speech": "한 번에 길게·비유"},
       "꿀 같은 액체 · 노랑 · 반짝(광택) · 한 컵 · 천천히 흘러내림 · 목→가슴 안"),

    # ── 빛·불꽃 ─────────────────────────────────────────────────────────
    item("M25", "multi_turn", {
        "opening": "친구가 고맙다고 했던 순간이요. 가슴 한쪽이 환해요.",
        "location": "몸 안이요, 가슴 왼쪽이요.",
        "focus": "작은 빛이 있어요.",
        "fleshout": "하얀 빛이 콩닥콩닥 뛰듯이 밝아졌다 어두워졌다 해요. 구슬만 해요.",
    }, [
        g("light", "작은 빛"),
        g("color", "하얀 빛", "material.color", WHITE),
        g("brightness", "밝아졌다 어두워졌다 해요", "material.brightness", None),
        g("motion_type", "콩닥콩닥 뛰듯이", "motion.type", isin("pounding")),
        g("size", "구슬만 해요", "layout.size", rng(0.0, 0.25)),
        g("body_part", "가슴 왼쪽", "body.part", isin("chest", "heart")),
        g("body_layer", "몸 안이요", "body.layer", eq("inner")),
    ], {"form": ["light"], "color": ["basic"], "size": ["numeric_ref", "body"], "texture": ["glow"],
        "motion": ["pulsing"], "response": "all", "speech": "비유"},
       "작은 빛 · 하양 · 밝아졌다 어두워졌다 · 콩닥콩닥(맥동) · 구슬만 · 가슴 왼쪽"),

    item("M26", "multi_turn", {
        "opening": "음… 오랜만에 그림 그리던 때요. 배 안쪽이 따뜻해요.",
        "location": "몸 안이요. 배 한가운데요.",
        "focus": "불꽃 같은 게 있어요.",
        "fleshout": "촛불 불꽃처럼 생겼어요. 아래는 파랗고 위로 갈수록 주황색이에요. 하늘하늘 흔들려요.",
        "probe_size_shape": "손가락 한 마디만 해요.",
    }, [
        g("light", "불꽃 같은 게"),
        g("color", "주황색이에요", "material.color", ORANGE),
        g("color2", "아래는 파랗고"),
        g("motion_type", "하늘하늘 흔들려요", "motion.type", isin("swaying", "trembling")),
        g("size", "손가락 한 마디만 해요", "layout.size", rng(0.0, 0.25)),
        g("temperature", "따뜻해요"),
        g("body_part", "배 한가운데", "body.part", isin("belly")),
        g("body_layer", "몸 안이요", "body.layer", eq("inner")),
    ], {"form": ["light", "pointed"], "color": ["mixed"], "size": ["numeric_ref", "body"], "texture": ["glow"],
        "motion": ["trembling"], "response": "all", "speech": "머뭇거림·비유"},
       "촛불 불꽃 · 아래 파랑+위 주황 · 하늘하늘 흔들림 · 손가락 한 마디 · 배 안"),

    item("M27", "free_narrative", {
        "opening": "졸업식 날이 떠올라요. 머리 위 한 뼘쯤 높이에 눈이 부실 만큼 밝은 노란빛이 떠 있어요. 크기는 냄비 뚜껑만 하고, 느긋하게 원을 그리며 돌아요. 가장자리는 흐려서 뒤가 살짝 비쳐요.",
        "location": "몸 주변이요.",
        "focus": "계속 떠 있어요.",
        "fleshout": "따뜻한 느낌이에요.",
    }, [
        g("light", "노란빛이 떠 있어요"),
        g("color", "노란빛", "material.color", YELLOW),
        g("brightness", "눈이 부실 만큼 밝은", "material.brightness", rng(0.8, 1.0)),
        g("height", "머리 위 한 뼘쯤 높이에", "layout.verticalOffset", rng(0.9, 1.0)),
        g("size", "냄비 뚜껑만 하고", "layout.size", rng(0.3, 0.65)),
        g("motion_type", "원을 그리며 돌아요", "motion.type", isin("circling", "rotating")),
        g("motion_speed", "느긋하게", "motion.speed", rng(0.0, 0.4)),
        g("opacity", "가장자리는 흐려서 뒤가 살짝 비쳐요", "material.opacity", None),
        g("body_layer", "몸 주변이요", "body.layer", isin(*AROUND)),
    ], {"form": ["light"], "color": ["basic"], "size": ["numeric_ref", "height"], "texture": ["glow", "partial_transparent"],
        "motion": ["floating"], "response": "all", "speech": "한 번에 길게"},
       "빛 · 노랑 · 눈부심 · 냄비 뚜껑만 · 머리 위 한 뼘 · 원을 그리며 돎 · 가장자리만 비침",
       distractors=[("졸업식", "떠올린 상황(맥락)")]),

    # ── 구멍·빈 것 ─────────────────────────────────────────────────────
    item("M28", "multi_turn", {
        "opening": "음… 이번 달 내내요. 가슴이 뻥 뚫린 것 같아요.",
        "location": "몸 안이요.",
        "focus": "구멍이 있어요.",
        "fleshout": "가슴 한가운데 동그란 구멍이 나 있어요. 안은 깜깜해요. 바람이 지나가는 느낌이에요.",
        "probe_size_shape": "도넛 하나 크기요.",
        "probe_movement": "아니요, 그대로예요.",
    }, [
        g("hole", "동그란 구멍"),
        g("brightness", "안은 깜깜해요", "material.brightness", rng(0.0, 0.25)),
        g("size", "도넛 하나 크기요", "layout.size", rng(0.05, 0.45)),
        g("motion_type", "그대로예요", "motion.type", isin("still")),
        g("body_part", "가슴 한가운데", "body.part", isin("chest")),
        g("body_layer", "몸 안이요", "body.layer", eq("inner")),
    ], {"form": ["hole", "round"], "color": [], "size": ["numeric_ref", "body"], "texture": ["dark"],
        "motion": ["still"], "response": "partial", "speech": "머뭇거림"},
       "구멍 · 안은 깜깜 · 도넛 크기 · 그대로 · 가슴 안"),

    item("M29", "multi_turn", {
        "opening": "주말에 혼자 집에 있던 오후요. 배 속이 텅 빈 것 같아요.",
        "location": "몸 안이요. 배 속이요.",
        "focus": "비어 있어요. 아무것도 없는 공간이요.",
        "fleshout": "텅 빈 공간이에요. 색은 없고, 그냥 비어 있어요. 배 전체만큼 넓어요.",
        "probe_movement": "가끔 넓어졌다 좁아졌다 해요.",
    }, [
        g("hole", "텅 빈 공간이에요"),
        g("color", "색은 없고", "material.color", eq(None)),
        g("size", "배 전체만큼 넓어요", "layout.size", rng(0.4, 0.8)),
        g("motion_type", "넓어졌다 좁아졌다 해요", "motion.type", None),
        g("body_part", "배 속이요", "body.part", isin("belly")),
        g("body_layer", "몸 안이요", "body.layer", eq("inner")),
    ], {"form": ["hole"], "color": ["none"], "size": ["relative", "body"], "texture": [],
        "motion": ["grow_shrink"], "response": "partial", "speech": "보통"},
       "텅 빈 공간 · 색 없음 · 배 전체만큼 · 넓어졌다 좁아졌다 · 배 안"),

    # ── 사람·동물 같은 구체물 ───────────────────────────────────────────
    item("M30", "multi_turn", {
        "opening": "회식 자리에서 말을 못 했던 거요. 옆에 누가 있는 것 같아요.",
        "location": "몸 주변이요. 왼쪽 옆이요.",
        "focus": "작은 사람 모양이 쪼그려 앉아 있어요.",
        "fleshout": "무릎을 끌어안고 웅크린 작은 사람이에요. 잿빛이고 얼굴은 안 보여요. 제 무릎 높이 정도로 작아요.",
        "probe_movement": "아주 살짝 몸을 흔들어요.",
    }, [
        g("figure", "작은 사람 모양"),
        g("posture", "웅크린", "form.posture", isin("crouched", "curled", "cowering", "hunched")),
        g("color", "잿빛이고", "material.color", GRAY),
        g("size", "무릎 높이 정도로 작아요", "layout.size", rng(0.2, 0.55)),
        g("motion_type", "살짝 몸을 흔들어요", "motion.type", isin("swaying")),
        g("body_layer", "몸 주변이요", "body.layer", isin("around_side", "around")),
    ], {"form": ["figure"], "color": ["mid"], "size": ["relative"], "texture": [],
        "motion": ["trembling"], "response": "all", "speech": "보통"},
       "웅크린 작은 사람 · 잿빛 · 무릎 높이 · 살짝 흔들림 · 왼쪽 옆",
       distractors=[("회식 자리", "떠올린 상황(맥락)")]),

    item("M31", "multi_turn", {
        "opening": "퇴근하고 소파에 누웠을 때요. 다리 쪽에 뭔가 기대 있어요.",
        "location": "몸 주변이요. 다리 옆이요.",
        "focus": "고양이요.",
        "fleshout": "까만 고양이 한 마리가 다리에 몸을 붙이고 동그랗게 말려 있어요. 털이 보송보송해요. 숨 쉴 때마다 등이 오르락내리락해요.",
        "probe_size_shape": "보통 고양이만 해요.",
    }, [
        g("figure", "까만 고양이 한 마리"),
        g("color", "까만 고양이", "material.color", BLACK),
        g("posture", "동그랗게 말려 있어요", "form.posture", isin("curled")),
        g("softness", "털이 보송보송해요"),
        g("motion_type", "등이 오르락내리락해요", "motion.type", None),
        g("size", "보통 고양이만 해요", "layout.size", rng(0.3, 0.6)),
        g("body_part", "다리 옆이요", "body.part", isin("leg")),
        g("body_layer", "몸 주변이요", "body.layer", isin("around_side", "around")),
    ], {"form": ["figure"], "color": ["basic"], "size": ["numeric_ref"], "texture": ["soft"],
        "motion": ["pulsing"], "response": "all", "speech": "길게 풀어서"},
       "고양이 · 검정 · 동그랗게 말림 · 보송보송 · 숨 쉬듯 오르내림 · 다리 옆",
       distractors=[("소파", "떠올린 상황의 사물(맥락)")],
       live={"find": ["따뜻한 게 기대 있어요."],
             "flesh_out_extra": ["털이 까매요.", "동그랗게 말려 있어요.", "숨 쉬는 것처럼 오르내려요.", "그게 다예요."]}),

    item("M32", "multi_turn", {
        "opening": "합격 문자를 받았던 때요. 어깨가 간질간질해요.",
        "location": "몸 표면 위요. 오른쪽 어깨 위에 앉아 있어요.",
        "focus": "작은 새 같아요.",
        "fleshout": "참새만 한 작은 새예요. 몸은 하늘색인데 날개 끝은 노래요. 날개를 파닥파닥해요.",
    }, [
        g("figure", "작은 새"),
        g("size", "참새만 한", "layout.size", rng(0.0, 0.3)),
        g("color", "하늘색", "material.color", {"hue_deg": [180, 215], "s": [0.3, 1.0], "l": [0.55, 0.88]}),
        g("color2", "날개 끝은 노래요"),
        g("motion_type", "날개를 파닥파닥해요", "motion.type", None),
        g("body_part", "오른쪽 어깨 위", "body.part", isin("shoulder")),
        g("body_layer", "몸 표면 위요", "body.layer", isin("surface_above", "surface")),
    ], {"form": ["figure"], "color": ["mixed", "mid"], "size": ["numeric_ref", "body"], "texture": [],
        "motion": ["trembling"], "response": "all", "speech": "보통"},
       "작은 새 · 하늘색+날개 끝 노랑 · 참새만 · 파닥임 · 오른쪽 어깨 위"),

    # ── 응답 유형: 모르겠어요 / 형상 없이 느낌만 ─────────────────────────
    item("M33", "multi_turn", {
        "opening": "음… 잘 모르겠어요. 그냥 좀 멍해요.",
        "location": "모르겠어요.",
        "focus": "잘 모르겠어요.",
        "fleshout": "딱히 떠오르는 게 없어요.",
        "probe_size_shape": "그것도 모르겠어요.",
        "probe_color_brightness": "색도 모르겠어요.",
        "probe_movement": "움직임도 잘 모르겠어요.",
    }, [
        g("size", "그것도 모르겠어요", "layout.size", eq(None)),
        g("color", "색도 모르겠어요", "material.color", eq(None)),
        g("motion_type", "움직임도 잘 모르겠어요", "motion.type", eq(None)),
        g("feeling", "멍해요"),
    ], {"form": [], "color": ["unknown"], "size": ["unknown"], "texture": [],
        "motion": ["unknown"], "response": "dont_know", "speech": "짧게·머뭇거림"},
       "전부 모름(멍함) — 모든 슬롯 null이어야 함"),

    item("M34", "multi_turn", {
        "opening": "어제 회의요. 답답해요.",
        "location": "가슴 안이요.",
        "focus": "계속 답답해요.",
        "fleshout": "그냥 답답하고 꽉 막힌 느낌이에요.",
        "probe_size_shape": "그런 건 없어요.",
        "probe_color_brightness": "색 같은 건 없어요.",
        "probe_movement": "모르겠어요.",
    }, [
        g("feeling", "꽉 막힌 느낌이에요"),
        g("size", "그런 건 없어요", "layout.size", eq(None)),
        g("color", "색 같은 건 없어요", "material.color", eq(None)),
        g("motion_type", "모르겠어요", "motion.type", eq(None)),
        g("body_part", "가슴 안이요", "body.part", isin("chest")),
        g("body_layer", "가슴 안이요", "body.layer", eq("inner")),
    ], {"form": [], "color": ["none"], "size": ["unknown"], "texture": [],
        "motion": ["unknown"], "response": "feeling_only", "speech": "짧게"},
       "형상 없음 · 답답함(느낌만) · 가슴 안 — 형태·색·크기 null이어야 함",
       distractors=[("어제 회의", "떠올린 상황(맥락)")]),

    item("M35", "multi_turn", {
        "opening": "월말 정산하던 때요. 몸이 무겁고 처져요.",
        "location": "몸 전체요. 안쪽이요.",
        "focus": "그냥 무거워요.",
        "fleshout": "뭔가 모양은 없고, 무겁게 가라앉는 느낌만 있어요.",
        "probe_size_shape": "모양은 없어요. 몸 전체만큼이요.",
        "probe_color_brightness": "어두운 느낌이에요.",
        "probe_movement": "아래로 가라앉아요.",
    }, [
        g("feeling", "무겁게 가라앉는 느낌만"),
        g("shape", "모양은 없고", negated=True),
        g("size", "몸 전체만큼이요", "layout.size", rng(0.6, 1.0)),
        g("brightness", "어두운 느낌이에요", "material.brightness", rng(0.0, 0.4)),
        g("motion_type", "아래로 가라앉아요", "motion.type", isin("sinking", "settling")),
        g("body_part", "몸 전체요", "body.part", isin("whole_body", "body")),
        g("body_layer", "안쪽이요", "body.layer", eq("inner")),
    ], {"form": [], "color": [], "size": ["relative", "body"], "texture": ["dark"],
        "motion": ["dripping"], "response": "feeling_only", "speech": "보통"},
       "형상 없음 · 무거움(느낌) · 몸 전체만큼 · 어두움 · 가라앉음"),

    item("M36", "multi_turn", {
        "opening": "면접 보기 직전이요. 초조해요.",
        "location": "몸 안, 배 쪽이요.",
        "focus": "안절부절못하는 느낌이에요.",
        "fleshout": "뭐가 있다기보다 계속 들썩들썩해요.",
        "probe_size_shape": "크기는 없어요.",
        "probe_color_brightness": "색은 없어요.",
        "probe_movement": "계속 들썩거려요.",
    }, [
        g("feeling", "안절부절못하는 느낌"),
        g("size", "크기는 없어요", "layout.size", eq(None)),
        g("color", "색은 없어요", "material.color", eq(None)),
        g("motion_type", "계속 들썩들썩해요", "motion.type", isin("vibrating", "trembling", "moving")),
        g("body_part", "배 쪽이요", "body.part", isin("belly")),
        g("body_layer", "몸 안", "body.layer", eq("inner")),
    ], {"form": [], "color": ["none"], "size": ["unknown"], "texture": [],
        "motion": ["trembling"], "response": "feeling_only", "speech": "짧게"},
       "형상 없음 · 초조함(느낌) · 들썩들썩 · 배 안 — 색·크기 null이어야 함"),
]


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def check(items: list[dict]) -> list[str]:
    errs = []
    seen = set()
    for it in items:
        if it["id"] in seen:
            errs.append(f"{it['id']}: id 중복")
        seen.add(it["id"])
        joined = " ".join(v for v in it["replies"].values() if v)
        for gd in it["gold"]:
            if norm(gd["phrase"]) not in norm(joined):
                errs.append(f"{it['id']}: phrase 없음 — {gd['phrase']}")
        for d in it["distractors"]:
            if norm(d["phrase"]) not in norm(joined):
                errs.append(f"{it['id']}: distractor 없음 — {d['phrase']}")
    return errs


def main() -> None:
    errs = check(ITEMS)
    if errs:
        raise SystemExit("\n".join(errs))
    corpus = {
        "corpusId": "imagery-mock-forms",
        "version": "0.1.0",
        "synthetic": True,
        "authoredBy": "agent:mock-forms-writer",
        "note": ("합성 대사만 담은 확인용 목업 코퍼스입니다(AGENTS.md 6). 실제 참여자 응답이 아닙니다. "
                 "작성자(AI 에이전트)는 shared/lexicon과 매퍼 코드를 보지 않고 썼고, dev.json 문장을 베끼지 않았으며 heldout.json은 열지 않았습니다. "
                 "replies 키와 expect 규칙은 dev.json의 note와 같습니다. 추가 필드: tags(덮는 범주), expected(사람이 기대하는 속성 요약, 말한 것만), "
                 "live(조건 2 재생용 합성 답: find = Find 단계 LLM 질문에 대한 답, flesh_out_extra = Flesh out 둘째 질문부터의 답). "
                 "슬롯이 없는 형상(선·실·종이·천·액체·빛·구멍·사람·동물)과 둘째 색은 slot = null(no_slot)로 적었습니다. "
                 "맥동·흘러내림·커졌다 작아졌다처럼 v2 enum에 맞는 값이 뚜렷하지 않은 움직임은 expect = null입니다."),
        "items": ITEMS,
    }
    out = HERE / "mock_corpus.json"
    out.write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(ITEMS)}개 항목 → {out.name}")


if __name__ == "__main__":
    main()
