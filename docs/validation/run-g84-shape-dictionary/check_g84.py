"""G84 형태 사전 넓히기(shape_prompt_en 0.2.1 → 0.3.0) 점검. 합성 문장만 쓴다. LLM·GPU를 부르지 않는다.

같은 문장을 '더하기 전' 사전(git 8d0fa03의 0.2.1)과 '더한 뒤' 사전(작업 트리의 0.3.0)으로 규칙 그림 프롬프트에 넣고 견준다.
매퍼 spec은 실험 설정(experiment.toml, 백엔드만 offline)의 scene_builder로 만든다 — 세션이 [맞는 게 없어요] 뒤에 쓰는 것과 같다.

  1. 새 낱말이 규칙 프롬프트의 중심 명사로 나오는가(긍정 틀 3개)
  2. 새 낱말이 부정·과거·타인·가정·비유·걱정 문장에서 생성을 잘못 시작하게 하는가(더하기 전후 수)
  3. G81·G82 평가 세트(합성, eval2·eval3·offline)의 부류별 규칙 경로 결과 전후
  4. 동음이의어·형태가 아닌 쓰임 문장에서 새 항목이 잡히는가
  5. 규칙이 잡으면 G82 LLM을 부르지 않는가(rule_route) · G77 형태 칸이 열리지 않는가(no_shape_stated 아님)

  chatbot/.venv/Scripts/python.exe check_g84.py [--out check_results.json]
"""
import argparse
import collections
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "chatbot"))
from ifs_chatbot.config import load_config  # noqa: E402
from ifs_chatbot.controller import Runtime  # noqa: E402
from ifs_chatbot import none_gen as ng  # noqa: E402
from ifs_chatbot import llm_shape as ls  # noqa: E402
from ifs_chatbot.scene_builder import normalize_confirmed  # noqa: E402

BEFORE_COMMIT = "8d0fa03"
LEX_REL = "shared/lexicon/shape_prompt_en.v0.json"


def batchim(w):
    c = ord(w[-1]) - 0xAC00
    return 0 <= c < 11172 and c % 28 != 0


def forms(w):
    b = batchim(w)
    return {"ye": "이에요" if b else "예요", "ga": "이" if b else "가", "eun": "은" if b else "는",
            "yeoss": "이었어요" if b else "였어요", "myeon": "이면" if b else "면", "rago": "이라고" if b else "라고",
            "eul": "을" if b else "를"}


POSITIVE = ["{w}{ye}.", "{w} 같은 게 있어요.", "가슴 앞에 {w}{ga} 있어요."]
SHOULD_NOT = {
    "negated": ["{w}{eun} 아니에요.", "{w} 같은 건 없어요."],
    "past": ["예전에는 {w}{yeoss}.", "처음엔 {w} 같았어요."],
    "other": ["친구가 {w} 같대요.", "다들 그게 {w}{rago} 했어요."],
    "hypothetical": ["{w}{myeon} 좋겠어요.", "아마 {w}일 거예요."],
    "predicate_simile": ["{w}처럼 단단해요.", "{w}처럼 무거워요."],
    "worry": ["{w} 때문에 걱정이에요.", "어제 {w}{eul} 잃어버려서 속상해요."],
}
HOMONYM = [  # (문장, 무엇을 보는가) — 새 항목이 잡히면 오탐
    ("다리가 붓고 아파요.", "붓(용언 붓다)"),
    ("얼굴이 부어 있어요.", "붓(용언 붓다)"),
    ("모자 사이가 좋아요.", "모자(어머니와 아들)"),
    ("동생이 나사에서 일해요.", "나사(NASA)"),
    ("유튜브를 오래 봐서 눈이 아파요.", "튜브(유튜브)"),
    ("먹이사슬 맨 위에 있는 느낌이에요.", "사슬(먹이사슬)"),
    ("블록체인 공부가 걱정이에요.", "블록(블록체인)"),
    ("일이 모자라요.", "모자(모자라다)"),
    ("시계 방향으로 돌아요.", "시계(방향 표현)"),
    ("동전 세 개 크기 정도요.", "동전(크기 비교)"),
    ("동전만 해요.", "동전(크기 비교 'N만 하다')"),
    ("수박만 한 크기예요.", "수박(크기 비교)"),
    ("의자에 앉아 있는 느낌이에요.", "의자(장소)"),
    ("이불 속에 들어가 있는 것 같아요.", "이불(장소)"),
    ("텐트 안에 있는 것 같아요.", "텐트(장소)"),
    ("울타리 밖에 있는 느낌이에요.", "울타리(장소)"),
    ("첫 단추를 잘못 끼운 느낌이에요.", "단추(관용 표현)"),
    ("깡통 전세 때문에 걱정이에요.", "깡통(관용 표현 깡통 전세)"),
    ("주사위는 던져졌어요.", "주사위(관용 표현)"),
    ("눈이 와요.", "눈덩이의 '눈' 단독"),
    ("양동작전 같아요.", "양동이의 앞부분"),
    ("판단이 안 서요.", "판·판때기 앞부분"),
]
WORRY_THEN_SHAPE = "{w} 때문에 요즘 신경 쓰여요.\n가슴이 답답해요.\n공 같은 게 있어요."
ALLOWED_STAGES = ls.ShapePrompt().allowed_stages                     # G82 프롬프트의 형태 단계(focus·flesh_out)
INTERVIEW_STAGE_RULE = ls.stage_rule({"status": "applied", "stages": ["find", "focus", "flesh_out"]}, ALLOWED_STAGES)
# 형태를 말했지만 지난 시제로 이야기한 문장(검증기 규칙이 과거로 막는 알려진 한계를 잼)
POSITIVE_PAST_NARRATION = ["가슴에 {w}{ga} 있었어요.", "{w}{ga} 낡았어요."]
SPECIFIED = ["돌덩이는 아니에요.", "예전에는 돌덩이였어요.", "돌덩이처럼 단단해요."]


class Probe:
    def __init__(self):
        logs = tempfile.mkdtemp(prefix="ifs-g84-check-")
        cfg = load_config("experiment").with_overrides(**{"llm.backend": "offline", "guard.model_backend": "none",
                                                           "session.log_dir": logs, "preview.mode": "none"})
        self.rt = Runtime(cfg)
        self.pm = ng._load_prompts()
        self.spec_cache = {}
        raw = subprocess.run(["git", "-C", str(REPO), "show", f"{BEFORE_COMMIT}:{LEX_REL}"], capture_output=True,
                             check=True).stdout.decode("utf-8")
        self.before_path = Path(tempfile.mkdtemp(prefix="ifs-g84-lex-")) / "shape_prompt_en.before.json"
        self.before_path.write_text(raw, encoding="utf-8")
        self.after_path = REPO / LEX_REL
        before = json.loads(raw)
        after = json.loads(self.after_path.read_text(encoding="utf-8"))
        old = {tuple(e["ko"]) for e in before["entries"]}
        self.added = [e for e in after["entries"] if tuple(e["ko"]) not in old]
        self.added_keys = {"+".join(e["ko"]) for e in self.added}
        self.versions = {"before": before["lexiconVersion"], "after": after["lexiconVersion"]}
        self.rts = {}

    def use(self, which):
        if which not in self.rts:
            self.rts[which] = self.pm._ShapeRuntime(self.before_path if which == "before" else self.after_path)
        self.pm._shape_rt = self.rts[which]
        self.pm._en_mod_block = None

    def spec(self, norm):
        if norm not in self.spec_cache:
            s = self.rt.scene_builder.build(norm, session_id="SYN-G84", participant_id="SYN")
            self.spec_cache[norm] = s if isinstance(s, dict) else s.to_dict()
        return self.spec_cache[norm]

    def run(self, text, which, stage_rule=None):
        self.use(which)
        norm = normalize_confirmed(text)
        p = self.pm.shape_prompt(norm, mapper_spec=self.spec(norm), stage_rule=stage_rule)
        call, why = ls.rule_route(self.pm, p)
        toks = [t for t in p.get("tokens") or [] if t.get("slot") != "template"]
        return {"status": p["status"], "blockReason": p["blockReason"], "text": p["text"],
                "starts": p["status"] == "ok",                       # [맞는 게 없어요] 뒤 규칙만으로 생성이 시작됨
                "g82Call": call, "g82Route": why,
                "g77ShapeSlotOpen": p["blockReason"] == "no_shape_stated",
                "tokens": [(t["ko"], t["en"], t.get("lexiconKey")) for t in toks],
                "newTokens": [(t["ko"], t["en"]) for t in toks if t.get("lexiconKey") in self.added_keys],
                "dropped": [(d["ko"], d["reason"]) for d in p["dropped"]]}

    def both(self, text, stage_rule=None):
        return {"text": text, "before": self.run(text, "before", stage_rule), "after": self.run(text, "after", stage_rule)}


def words_of(added):
    """새 항목 → 낱말(붙여 쓴 꼴) 목록. 같은 낱말의 나뉜 꼴은 하나로."""
    out = {}
    for e in added:
        out.setdefault("".join(e["ko"]), e["en"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "check_results.json"))   # results.json은 실제 흐름(run_g84_e2e.py) 것
    a = ap.parse_args()
    P = Probe()
    words = words_of(P.added)
    res = {"what": "G84 shape dictionary check (synthetic texts only)", "lexicon": P.versions,
           "beforeCommit": BEFORE_COMMIT, "addedEntries": len(P.added), "addedWords": len(words)}

    # 1. 긍정 틀
    pos, pos_fail = [], []
    for w, en in words.items():
        f = forms(w)
        for tmpl in POSITIVE:
            r = P.both(tmpl.format(w=w, **f))
            ok = r["after"]["starts"] and any(t[0].startswith(w) or w in t[0] for t in r["after"]["newTokens"]) \
                and r["after"]["tokens"][-1][1] == en and not r["after"]["g82Call"] and not r["after"]["g77ShapeSlotOpen"]
            r.update(word=w, en=en, ok=ok)
            pos.append(r)
            if not ok:
                pos_fail.append({"text": r["text"], "after": r["after"]})
    res["positive"] = {"sentences": len(pos), "ok": sum(r["ok"] for r in pos),
                       "beforeStarts": sum(r["before"]["starts"] for r in pos),
                       "afterStarts": sum(r["after"]["starts"] for r in pos),
                       "beforeG82Calls": sum(r["before"]["g82Call"] for r in pos),
                       "afterG82Calls": sum(r["after"]["g82Call"] for r in pos),
                       "afterG77ShapeSlotOpen": sum(r["after"]["g77ShapeSlotOpen"] for r in pos),
                       "fail": pos_fail}

    # 1b. 형태를 말했지만 지난 시제·'낡았어요'(과하게 막히는 수)
    pp = []
    for w in words:
        f = forms(w)
        for tmpl in POSITIVE_PAST_NARRATION:
            pp.append(P.both(tmpl.format(w=w, **f)))
    res["positivePastNarration"] = {"sentences": len(pp), "beforeStarts": sum(r["before"]["starts"] for r in pp),
                                    "afterStarts": sum(r["after"]["starts"] for r in pp),
                                    "afterDroppedReasons": dict(collections.Counter(d[1] for r in pp for d in r["after"]["dropped"]))}

    # 2. 생성을 시작하면 안 되는 틀
    bad = {}
    for kind, tmpls in SHOULD_NOT.items():
        rows = []
        for w in words:
            f = forms(w)
            for tmpl in tmpls:
                rows.append(P.both(tmpl.format(w=w, **f)))
        reasons = collections.Counter(d[1] for r in rows for d in r["after"]["dropped"])
        bad[kind] = {"sentences": len(rows), "beforeStarts": sum(r["before"]["starts"] for r in rows),
                     "afterStarts": sum(r["after"]["starts"] for r in rows),
                     "afterStartsWithNewWord": sum(bool(r["after"]["starts"] and r["after"]["newTokens"]) for r in rows),
                     "beforeG82Calls": sum(r["before"]["g82Call"] for r in rows),
                     "afterG82Calls": sum(r["after"]["g82Call"] for r in rows),
                     "afterDroppedReasons": dict(reasons),
                     "examplesStarted": [r["text"] for r in rows if r["after"]["starts"]][:6],
                     "examplesBlocked": [(r["text"], r["after"]["dropped"]) for r in rows if not r["after"]["starts"]][:3]}
    res["shouldNotStart"] = bad
    # 2b. 걱정 줄에 새 낱말 + 형상 줄에 기존 사전 낱말(공): 중심 명사는 처음 나온 형태 명사라 걱정 줄 낱말이 공을 밀어낼 수 있다
    stolen = []
    for w in words:
        t = WORRY_THEN_SHAPE.format(w=w)
        r = P.both(t, INTERVIEW_STAGE_RULE)          # 세 줄 = 면담 세 단계 답(확정 텍스트를 고치지 않은 세션)
        stolen.append({"text": t, "beforeHead": (r["before"]["tokens"] or [[None, None]])[-1][1],
                       "afterHead": (r["after"]["tokens"] or [[None, None]])[-1][1]})
    res["worryThenShape"] = {"sentences": len(stolen), "beforeHeadBall": sum(x["beforeHead"] == "ball" for x in stolen),
                             "afterHeadBall": sum(x["afterHead"] == "ball" for x in stolen),
                             "afterHeadNewWord": sum(x["afterHead"] not in ("ball", None) for x in stolen),
                             "examples": stolen[:3]}
    res["specified"] = [P.both(t) for t in SPECIFIED]

    # 3. 평가 세트(합성)
    ev = {}
    sets = []
    for name in ("run-g82-llm-shape-eval2", "run-g82-llm-shape-eval3"):
        d = json.loads((HERE.parent / name / "cases.json").read_text(encoding="utf-8"))
        # 단계 표지: 그 평가에서 세션이 얻은 lineStages(applied면 그 단계, 아니면 단계 규칙 없음)
        rr = json.loads((HERE.parent / name / "results.json").read_text(encoding="utf-8"))
        rows = next(v for v in rr.values() if isinstance(v, list) and len(v) > 100)
        st = {x["id"]: ls.stage_rule(x.get("lineStages"), ALLOWED_STAGES) for x in rows}
        sets += [(name, c["group"], c["expect"], "\n".join(c["lines"]), st.get(c["id"])) for c in d["cases"]]
    sys.path.insert(0, str(HERE.parent / "run-g82-llm-shape-offline"))
    import run_g82 as off  # noqa: E402
    sets += [("run-g82-llm-shape-offline", g, exp, t, None) for _cid, g, t, exp, _ko, _en in off.CASES]   # 고친 확정 → 단계 없음
    for name, group, expect, text, srule in sets:
        r = P.both(text, srule)
        k = f"{name.replace('run-g82-llm-shape-', '')}:{group}:{expect}"
        e = ev.setdefault(k, {"cases": 0, "beforeStarts": 0, "afterStarts": 0, "beforeG82Calls": 0, "afterG82Calls": 0,
                              "examplesAfterStarts": []})
        e["cases"] += 1
        e["beforeStarts"] += r["before"]["starts"]
        e["afterStarts"] += r["after"]["starts"]
        e["beforeG82Calls"] += r["before"]["g82Call"]
        e["afterG82Calls"] += r["after"]["g82Call"]
        if r["after"]["starts"] and not r["before"]["starts"] and expect != "fill" and len(e["examplesAfterStarts"]) < 4:
            e["examplesAfterStarts"].append(text.split("\n")[-1])
    res["evalSets"] = ev

    # 4. 동음이의어·형태가 아닌 쓰임
    hom = []
    for t, what in HOMONYM:
        r = P.both(t)
        hom.append({"text": t, "what": what, "newTokensAfter": r["after"]["newTokens"], "startsBefore": r["before"]["starts"],
                    "startsAfter": r["after"]["starts"], "dropped": r["after"]["dropped"]})
    res["homonym"] = {"sentences": len(hom), "caughtNewWord": sum(bool(h["newTokensAfter"]) for h in hom), "rows": hom}

    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k in ("lexicon", "addedEntries", "addedWords")}, ensure_ascii=False))
    print("positive", {k: v for k, v in res["positive"].items() if k != "fail"})
    print("positivePastNarration", res["positivePastNarration"])
    for f in res["positive"]["fail"]:
        print("  FAIL", f["text"], f["after"]["status"], f["after"]["blockReason"], f["after"]["tokens"], f["after"]["dropped"])
    for k, v in bad.items():
        print("shouldNot", k, {x: v[x] for x in ("sentences", "beforeStarts", "afterStarts", "afterStartsWithNewWord",
                                                 "beforeG82Calls", "afterG82Calls", "afterDroppedReasons")})
        print("   started e.g.", v["examplesStarted"][:4])
    for s in res["specified"]:
        print("specified", s["text"], "before", s["before"]["starts"], "after", s["after"]["starts"], s["after"]["tokens"],
              s["after"]["dropped"])
    for k, v in sorted(ev.items()):
        print("eval", k, {x: v[x] for x in ("cases", "beforeStarts", "afterStarts", "beforeG82Calls", "afterG82Calls")},
              v["examplesAfterStarts"][:2])
    print("worryThenShape", {k: v for k, v in res["worryThenShape"].items() if k != "examples"})
    print("homonym", res["homonym"]["sentences"], "caught", res["homonym"]["caughtNewWord"])
    for h in hom:
        print("  ", h["text"], h["newTokensAfter"], h["startsAfter"], h["dropped"])


if __name__ == "__main__":
    main()
