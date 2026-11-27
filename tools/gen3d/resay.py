"""G73 CP13a: 다시 적은 글 → 갈래·형태 프롬프트·덮어쓰기 값(생성기는 갈래 solid이고 프롬프트가 통과할 때만 부른다).

흐름(run_resay):
  설정 꺼짐 → 아무것도 하지 않음(disabled)
  위기 키워드(안전 사전) → 매핑·프롬프트·생성기 모두 건너뜀(crisis). 고정 문구는 서버가 낸다(CP13b, 원칙 4)
  재진술 매핑(chatbot ifs_chatbot/resay.py) → 갈래 + 허용 슬롯 값(덮어쓰기 처음 값)
  갈래 solid → 형태 프롬프트(resay_prompts): 손 형태 사전 → 대역 사전 → WordNet 거르개 → 사람 닮은 사물 차단 → 판정 불가면 차단
             → 통과한 프롬프트마다 생성기 호출(뜻이 2개면 뜻마다 하나, 회당 최대 resay_candidates개)
  갈래 mist·light·flame·blocked·none → 생성기를 부르지 않는다(값만)

LLM·번역 모델을 쓰지 않는다(원칙 1). 프롬프트의 모든 내용 낱말은 다시 적은 글의 글자 위치로 거슬러 간다(G62 감사 재사용).
생성기는 인자로 받는다(이 모듈은 모델을 불러오지 않음). 시험은 가짜 생성기로 돈다.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prompts  # noqa: E402
from bilingual import BilingualDict  # noqa: E402
from common import CHATBOT  # noqa: E402
from wordnet_filter import WordNetFilter  # noqa: E402

sys.path.insert(0, str(CHATBOT))
RESAY_PROMPT_VERSION = "gen3d-resay-prompt/0.2.0"
FILTER_PATH = CHATBOT.parent / "shared" / "lexicon" / "resay_prompt_filter.v0.json"
_FORM_POSITIONS = ("head", "simile", "noun_modifier")


def load_filter(path: Path = FILTER_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _words(en: str) -> list[str]:
    base = en[:-5] if en.endswith("-like") else en
    return [w for w in re.split(r"[ \-]+", base.lower()) if w]


def _blocked(base: dict, reason: str, detail: list[str]) -> dict:
    return {**base, "status": "blocked", "blockReason": reason, "blockDetail": ";".join(sorted(set(detail))) or None,
            "prompts": []}


def resay_prompts(text: str, mapping: dict, *, bilingual: BilingualDict | None, wordnet: WordNetFilter,
                  filt: dict | None = None) -> dict:
    """갈래 solid인 다시 적은 글 → 형태 프롬프트 0–2개. 같은 글·같은 사전(판·sha256)·같은 WordNet → 같은 결과."""
    filt = filt or load_filter()
    base = {"promptVersion": RESAY_PROMPT_VERSION, "filter": f"{filt['lexiconId']}@{filt['tableVersion']}",
            "bilingualDict": bilingual.info() if bilingual else None, "wordnet": wordnet.info(),
            "sourceTextSha256": mapping["sourceTextSha256"], "words": []}
    if mapping["branch"] != "solid":
        return {**base, "status": "not_solid", "blockReason": None, "blockDetail": None, "prompts": []}
    core = prompts._shape_core(text)
    if prompts.sha256_text(core["norm"]) != mapping["sourceTextSha256"]:
        raise ValueError("매핑과 프롬프트의 정규화 글이 다릅니다")
    if core["detail"]:                                  # G62와 같은 차단(사람·동물·제외 범주·메시로 안 되는 범주)
        return _blocked(base, "excluded_category", core["detail"])
    toks = core["toks"]
    start_of = {t.start: k for k, t in enumerate(toks)}
    end_of = {t.end: k for k, t in enumerate(toks)}
    hl_en = set(filt["humanlike"]["en"])
    pat = re.compile(filt["bilingual"]["pattern"])
    max_senses = filt["bilingual"]["maxSenses"]

    accepted_bi: list[dict] = []
    dropped_bi: list[dict] = []
    unresolved_heads: list[str] = []
    ambiguous = None
    for w in mapping["formWords"]:
        if w["kind"] != "unlisted" or w["position"] not in _FORM_POSITIONS:
            continue
        rec = {"ko": w["ko"], "charSpan": w["charSpan"], "position": w["position"], "source": "bilingual_dict"}
        base["words"].append(rec)

        def drop(reason: str) -> None:
            rec["result"] = reason
            dropped_bi.append({"ko": w["ko"], "charSpan": w["charSpan"], "reason": reason})
            if w["position"] == "head":
                unresolved_heads.append(f"{reason}:{w['ko']}")

        if bilingual is None:
            drop("no_bilingual_dict")
            continue
        entry = bilingual.lookup(w["ko"])
        if entry is None:
            drop("not_in_bilingual_dict")
            continue
        rec["dictEntryId"] = entry["id"]
        cands = []
        for en in entry["translations"]:
            en_n = en.strip().lower()
            if not pat.match(en_n) or len(en_n.split()) > filt["bilingual"]["maxWords"]:
                continue                                 # 설명 문장·괄호는 버림
            if en_n not in cands:
                cands.append(en_n)
        judged = []
        for en in cands:
            hl = [x for x in _words(en) if x in hl_en] + ([en] if en in hl_en else [])
            if hl:
                rec["result"] = "blocked"
                return _blocked(base, "humanlike_object", [f"humanlike_en:{w['ko']}>{en}"])
            j = wordnet.judge(en)
            judged.append(j)
            if j["verdict"] == "block":
                rec["result"] = "blocked"
                return _blocked(base, "wordnet_category", [f"wordnet:{j['reason']}:{w['ko']}>{en}"])
        rec["judged"] = judged
        passing = [j for j in judged if j["verdict"] == "pass"]
        if not passing:
            reasons = sorted({j["reason"] or j["verdict"] for j in judged}) or ["no_usable_translation"]
            drop("no_passing_translation(" + ",".join(reasons) + ")")
            continue
        if len(passing) > max_senses:
            drop("ambiguous_sense")
            continue
        if len(passing) == 2:
            if ambiguous is not None:
                drop("second_ambiguity")
                continue
            ambiguous = w["ko"]
        i, jx = start_of.get(w["charSpan"][0]), end_of.get(w["charSpan"][1])
        if i is None or jx is None:
            drop("untraceable")
            continue
        rec["result"] = "accepted"
        accepted_bi.append({"i": i, "j": jx, "ko": w["ko"], "span": list(w["charSpan"]), "pos": w["position"],
                            "senses": [(p["en"], p["synset"]) for p in passing], "dictEntryId": entry["id"]})

    # G73-j fail closed: 판정 못 한 중심 명사가 하나라도 있으면 다른 중심 명사(손 사전·대역 사전)가 잡혀도 막는다.
    # 판정 못 한 낱말을 빼고 남은 낱말로 만들면 참여자가 말한 사물이 아닌 것을 만든다(CP13 지적 2).
    if unresolved_heads:
        return _blocked(base, "unjudged_head_noun", unresolved_heads)

    n_variants = max([len(a["senses"]) for a in accepted_bi] or [1])
    out_prompts = []
    for v in range(n_variants):
        acc = list(core["accepted"])
        sense = None
        for a in accepted_bi:
            en, syn = a["senses"][v] if len(a["senses"]) > 1 else a["senses"][0]
            if len(a["senses"]) > 1:
                sense = {"ko": a["ko"], "en": en, "index": v, "of": len(a["senses"])}
            e = {"ko": [a["ko"]], "pos": "noun", "en": en, "slot": "shape_noun", "source": "bilingual_dict",
                 "dictEntryId": a["dictEntryId"], "wordnet": syn}
            acc.append({"i": a["i"], "j": a["j"], "e": e, "ko": a["ko"], "span": a["span"], "pos": a["pos"]})
        acc.sort(key=lambda a: a["i"])
        p = prompts._assemble(core, acc, core["dropped"] + dropped_bi, [], limits=filt["promptLimits"])
        for t in p["tokens"]:
            if t["slot"] != "template" and "source" not in t:
                t["source"] = "lexicon"
        # 감사(영어 쪽): 사람 닮은 사물 낱말이 하나도 없어야 한다
        bad = [t["en"] for t in p["tokens"] if t["slot"] != "template" and any(x in hl_en for x in _words(t["en"]))]
        if bad:
            return _blocked(base, "audit_humanlike_token", [f"token:{b}" for b in bad])
        if p["status"] != "ok":
            return _blocked(base, p["blockReason"], (p["blockDetail"] or "").split(";") if p["blockDetail"] else [])
        p["sense"] = sense
        out_prompts.append(p)
    return {**base, "status": "ok", "blockReason": None, "blockDetail": None, "prompts": out_prompts}


class ResayPipeline:
    """설정 + 매퍼 + 사전들을 묶은 실행기. generator(text, negative_text, seed) → 아무 값(가짜 생성기로 시험)."""

    def __init__(self, gen3d_cfg, *, mapper=None, bilingual: BilingualDict | None = None,
                 wordnet: WordNetFilter | None = None, safety=None, filt: dict | None = None,
                 safety_lexicon: str | None = None):
        """safety_lexicon: 안전 사전 파일 이름(shared/lexicon/, 예 설정 [guard] safety_lexicon). 비우면 SafetyLexicon 기본."""
        self.cfg = gen3d_cfg
        self.safety_lexicon = safety_lexicon
        self.filt = filt or load_filter()
        self._mapper = mapper
        self.bilingual = bilingual
        self.wordnet = wordnet
        self._safety = safety

    @property
    def enabled(self) -> bool:
        return bool(getattr(self.cfg, "resay", False))

    def _ready(self) -> None:
        if self._mapper is None:
            from ifs_chatbot.korean import Analyzer
            from ifs_chatbot.resay import ResayMapper
            self._mapper = ResayMapper(Analyzer())
        if self._safety is None:
            from ifs_chatbot.paths import shared
            from ifs_chatbot.safety import SafetyLexicon
            self._safety = SafetyLexicon(shared("lexicon", self.safety_lexicon) if self.safety_lexicon else None)
        if self.wordnet is None:
            self.wordnet = WordNetFilter.auto(self.filt)
        if self.bilingual is None and getattr(self.cfg, "resay_bilingual_dict", ""):
            self.bilingual = BilingualDict.load(self.cfg.resay_bilingual_dict)

    def run(self, text: str, *, round_no: int = 1, generator=None, seed_base: int = 0) -> dict:
        if not self.enabled:
            return {"status": "disabled", "generatorCalls": 0}
        max_rounds = int(self.cfg.resay_max_rounds)
        if round_no < 1 or round_no > max_rounds:
            return {"status": "round_limit", "round": round_no, "maxRounds": max_rounds, "generatorCalls": 0}
        self._ready()
        hits = self._safety.crisis_hits(text)
        if hits:                                         # 원칙 4: 위기 뒤에는 매핑·생성기·LLM을 부르지 않는다
            return {"status": "crisis", "round": round_no, "crisisIds": sorted({h.id for h in hits}),
                    "generatorCalls": 0}
        mapping = self._mapper.map(text)
        out = {"status": "ok", "round": round_no, "branch": mapping["branch"], "mapping": mapping, "prompt": None,
               "candidates": [], "generatorCalls": 0}
        if mapping["branch"] != "solid":
            return out
        pr = resay_prompts(text, mapping, bilingual=self.bilingual, wordnet=self.wordnet, filt=self.filt)
        out["prompt"] = pr
        if pr["status"] != "ok":
            return out
        if generator is None:
            out["status"] = "no_generator"
            return out
        for k, p in enumerate(pr["prompts"][:int(self.cfg.resay_candidates)]):
            seed = seed_base + round_no * 10 + k
            res = generator(p["text"], p["negativeText"], seed)
            out["generatorCalls"] += 1
            out["candidates"].append({"k": k, "seed": seed, "sense": p["sense"], "result": res})
        return out
