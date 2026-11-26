"""연구자 승인형 1층 사전 확장 도구 (G61 ③). 실행 경로(매퍼)는 바꾸지 않는다 — 이 도구는 오프라인에서 후보를 보여 주고,
연구자가 승인한 항목만 새 사전 버전 파일로 합친다. 임베딩·외부 API·LLM을 쓰지 않는다(후보 = 자모 편집거리, 형태 변이
규칙, 같은 형태소). 같은 입력은 같은 출력이다.

명령
  collect  장면 파일(SceneSpec JSON)·세션 기록 폴더·합성 코퍼스에서 _unmatched·_unmapped·_needsConfirmation을 모아 빈도표와
           후보를 붙인 proposals 파일을 쓴다(각 항목 decision.status = proposed, 승인자·날짜 빈칸).
  seed     낱말 목록(JSON: 문자열 목록 또는 {"words": [...]})으로 같은 형식의 proposals 파일을 쓴다(합성 후보 검토용).
  merge    proposals 파일에서 decision.status = approved인 항목만 1층 사전 오버레이의 새 버전 파일로 합친다
           (버전 올림, 항목마다 출처·승인자·날짜). 승인자·날짜가 비었거나 범주·품사·값이 맞지 않으면 멈춘다.

참여자 데이터(AGENTS.md 6): 세션 기록·장면 파일에서 만든 proposals는 참여자 데이터다. 기본 출력 폴더는 git이 무시하는
chatbot/logs/lexicon-proposals/ 이고, --out으로 저장소 안(.gitignore 밖)을 고르면 경고한다. 저장소에는 합성 자료로 만든
예시만 둔다(docs/validation/lexicon-proposals/).

실행(저장소 루트에서, 챗봇 가상환경 python):
  chatbot\\.venv\\Scripts\\python.exe tools\\lexicon_proposals.py collect chatbot\\logs\\scenes
  chatbot\\.venv\\Scripts\\python.exe tools\\lexicon_proposals.py collect --corpus chatbot\\tests\\fixtures\\imagery_corpus\\dev.json
  chatbot\\.venv\\Scripts\\python.exe tools\\lexicon_proposals.py seed words.json --source "synthetic, 연구자 검토 전"
  chatbot\\.venv\\Scripts\\python.exe tools\\lexicon_proposals.py merge <proposals.json> --version 2.1.0
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "chatbot"))

from ifs_chatbot.jamo import decompose, levenshtein  # noqa: E402
from ifs_chatbot.korean import Analyzer  # noqa: E402
from ifs_chatbot.lexicon import LexEntry  # noqa: E402
from ifs_chatbot.paths import shared  # noqa: E402
from ifs_chatbot.scene_builder_v2 import load_lexicon_chain  # noqa: E402
from ifs_chatbot.variants import VariantRules  # noqa: E402

FORMAT = "ifs-lexicon-proposals/0.1"
DEFAULT_OUT = REPO / "chatbot" / "logs" / "lexicon-proposals"
CONTENT_TAGS = {"NNG", "NNP", "VA", "VV", "XR", "MAG"}
POS_OK = {"NNG", "NNP", "NP", "VA", "VV", "XR", "MAG"}
SKIP_CATS = {"color", "dimension"}          # 색은 표면형 규칙(scene_params.v1 colorTerms)이 맡고, 차원어는 V5 전용
DEFAULT_CHAIN = ["layer1_lexicon.v0.json", "layer1_lexicon.v1.json", "layer1_lexicon.v2.json"]
FUZZY_MAX = 2
FUZZY_TOP = 3


# ── 공통 ────────────────────────────────────────────────────────────────────
def _now() -> str:
    return _dt.date.today().isoformat()


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _in_git_tracked_area(path: Path) -> bool:
    """path가 저장소 안이고 .gitignore가 무시하지 않는 곳이면 True(참여자 데이터 경고용)."""
    try:
        path.resolve().relative_to(REPO)
    except ValueError:
        return False
    try:
        r = subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", str(path.resolve())],
                           capture_output=True, timeout=10)
        return r.returncode != 0
    except (OSError, subprocess.SubprocessError):
        return True


def _not_attribute_words() -> frozenset[str]:
    """속성어가 아닌 줄 이미 아는 말(매퍼의 다른 규칙이 쓰는 말 + 불용 명사 + 기능어)."""
    from ifs_chatbot.extract import FUNCTION_LEMMAS
    out: set[str] = set(FUNCTION_LEMMAS)
    p1 = json.loads(shared("lexicon", "scene_params.v1.json").read_text(encoding="utf-8"))["v1"]
    for k in ("strong", "weak"):
        out |= set(p1["degreeAdverbs"][k])
    for k in ("uncertaintyMarkers", "correctionMarkers", "formerMarkers", "currentMarkers", "approxWords"):
        v = p1.get(k) or []
        out |= set(v if isinstance(v, list) else v.keys())
    p2 = json.loads(shared("lexicon", "scene_params.v2.json").read_text(encoding="utf-8"))["unlistedNouns"]
    out |= set(p2.get("unambiguousRecallVerbs", [])) | set(p2.get("sceneTimeNouns", []))
    stop = json.loads(shared("lexicon", "noun_stoplist.v2.json").read_text(encoding="utf-8"))
    for g in stop["groups"].values():
        out |= set(g["words"])
    out |= {"모르", "떠오르", "생각나", "기억나", "장면", "잘", "안", "못", "계속", "그대로", "그냥", "오", "가", "하", "되",
            "있", "없", "같", "보이", "느껴지", "느끼", "들"}
    return frozenset(out)


class Resources:
    def __init__(self, chain: list[str], variant_rules: str):
        self.analyzer = Analyzer()
        paths = [shared("lexicon", n) for n in chain]
        self.lexicon = load_lexicon_chain(self.analyzer, paths)
        self.chain = [f"{n} ({_sha(p)[:19]})" for n, p in zip(chain, paths)]
        self.variants = VariantRules(shared("lexicon", variant_rules))
        self.forms: list[tuple[str, list[str], LexEntry]] = []
        for e in self.lexicon.entries:
            if e.category in SKIP_CATS:
                continue
            for f in (e.lemma, *e.alt):
                self.forms.append((f, decompose(f), e))
        self.not_attribute = _not_attribute_words()

    def is_attribute_like(self, term: str) -> bool:
        """매퍼가 이미 다른 규칙으로 쓰는 말(정도 부사·모름·때 표지·회상 동사·불용 명사)은 사전 후보에서 뺀다."""
        return term not in self.not_attribute

    def lookup(self, form: str) -> list[LexEntry]:
        return self.lexicon._by_form.get(form, []) + self.lexicon._by_alt.get(form, [])

    @staticmethod
    def _entry(e: LexEntry) -> dict:
        return {"lemma": e.lemma, "pos": e.pos, "category": e.category, "value": e.value}

    def candidates(self, term: str, tag: str) -> list[dict]:
        out: list[dict] = []
        seen: set[tuple] = set()

        def add(d: dict) -> None:
            k = (d["via"], d["lemma"], d["category"], json.dumps(d["value"], sort_keys=True, ensure_ascii=False))
            if k not in seen:
                seen.add(k)
                out.append(d)

        # (1) 형태 변이 규칙으로 닿는 뿌리(매퍼와 같은 규칙 표)
        m = self.variants.resolve(term, tag if tag in self.variants.source_tags else "EOJEOL", None, self.lookup,
                                  lambda e: e.category not in SKIP_CATS)
        if m is not None:
            for e in m.entries:
                add({"via": "variant_rule", **self._entry(e), "rules": list(m.rules), "root": m.root,
                     "grade": list(m.grades)})
        # (2) 자모 편집거리 이웃(가까운 순 3개, 자모 5개 미만이면 거리 1, 아니면 2까지). 값 경로의 퍼지(거리 1, 동률 거부)보다
        #     넓게 — 연구자 검토용. 한 음절 낱말은 이웃이 너무 많아 붙이지 않는다
        tj = decompose(term)
        maxd = 1 if len(tj) < 5 else FUZZY_MAX
        if len(term) >= 2:
            scored = sorted(((levenshtein(tj, j), f, e) for f, j, e in self.forms if abs(len(j) - len(tj)) <= maxd),
                            key=lambda x: (x[0], x[1], x[2].category))
            for d, f, e in [x for x in scored if 0 < x[0] <= maxd][:FUZZY_TOP]:
                add({"via": "jamo_neighbor", **self._entry(e), "matched": f, "distance": d})
        # (3) 같은 형태소를 품은 항목: Kiwi 분석의 내용 형태소(2음절 이상)가 표제어와 같거나, 표제어가 낱말의 앞·뒤 조각일 때
        morphs = [t.form for t in self.analyzer.tokens(term) if t.base_tag in CONTENT_TAGS and len(t.form) >= 2]
        for f, _, e in self.forms:
            if f == term or len(f) < 2:
                continue
            if f in morphs or (len(term) > len(f) and (term.startswith(f) or term.endswith(f))):
                add({"via": "shared_morpheme", **self._entry(e), "matched": f})
        return out


def _blank_decision() -> dict:
    return {"status": "proposed", "lemma": None, "pos": None, "category": None, "value": None, "ex": None,
            "useCandidate": None, "approvedBy": "", "approvedOn": "", "note": ""}


# ── collect ─────────────────────────────────────────────────────────────────
def _iter_specs(node):
    """JSON 안의 SceneSpec 꼴 dict(meta + _unmatched + _unmapped)를 모두 찾는다."""
    if isinstance(node, dict):
        if "_unmatched" in node and "_unmapped" in node and isinstance(node.get("meta"), dict):
            yield node
            return
        for v in node.values():
            yield from _iter_specs(v)
    elif isinstance(node, list):
        for v in node:
            yield from _iter_specs(v)


def _corpus_specs(path: Path, builder) -> list[dict]:
    """합성 코퍼스(dev.json 형식: items[].replies) 또는 문자열 목록 JSON → 매퍼 v2(+ G61 기능)로 만든 spec."""
    d = json.loads(path.read_text(encoding="utf-8"))
    texts: list[str] = []
    if isinstance(d, list):
        texts = [x for x in d if isinstance(x, str)]
    elif isinstance(d.get("sentences"), list):
        texts = [x for x in d["sentences"] if isinstance(x, str)]
    else:
        for it in d.get("items", []):
            texts.append("\n".join(v for v in (it.get("replies") or {}).values() if v))
    return [builder.build(t) for t in texts if t.strip()]


def collect(args) -> Path:
    res = Resources(args.chain, args.variant_rules)
    specs: list[tuple[str, dict]] = []
    sources = []
    for p in map(Path, args.paths):
        files = sorted(p.rglob("*.json")) if p.is_dir() else [p]
        n0 = len(specs)
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            specs += [(f.name, s) for s in _iter_specs(data)]
        sources.append({"kind": "spec_files", "name": p.name, "files": len(files), "specs": len(specs) - n0})
    if args.corpus:
        from ifs_chatbot.scene_builder_v2 import SceneSpecBuilderV2
        b = SceneSpecBuilderV2(res.analyzer, ext_lexicon_path=shared("lexicon", args.chain[-1]) if len(args.chain) > 2 else None,
                               variant_rules_path=shared("lexicon", args.variant_rules))
        for c in map(Path, args.corpus):
            got = _corpus_specs(c, b)
            specs += [(c.name, s) for s in got]
            sources.append({"kind": "synthetic_corpus", "name": c.name, "specs": len(got), "mapper": b.info()["builder"]})
    counts: dict[tuple[str, str, str], dict] = {}
    for src, s in specs:
        terms: list[tuple[str, str, str, str]] = []
        for u in s.get("_unmatched") or []:
            if u.get("tag", "").split("-")[0] in CONTENT_TAGS:
                terms.append((u["lemma"], u["tag"].split("-")[0], "unmatched", "사전에 없음"))
        for u in s.get("_unmapped") or []:
            if u.get("category") == "unlisted_noun":
                terms.append((u["lemma"], "NNG", "unlisted_noun", "사전에 없는 명사"))
            elif u.get("reason") in ("no_scene_param", "no_value_mapping"):
                terms.append((u["lemma"], "-", f"no_scene_value:{u['category']}", f"사전에 있으나 장면 값 없음({u['reason']})"))
        for n in s.get("_needsConfirmation") or []:
            terms.append((n["trigger"], "EOJEOL", "needs_confirmation", f"자모 퍼지 후보 {n['matched']}(값 아님)"))
        seen_here = set()
        for lemma, tag, kind, why in terms:
            k = (lemma, tag, kind)
            c = counts.setdefault(k, {"count": 0, "specs": 0, "why": why})
            c["count"] += 1
            if k not in seen_here:
                c["specs"] += 1
                seen_here.add(k)
    items = []
    skipped: dict[str, int] = {}
    # 사전에 없는 말(낱말·명사·퍼지 후보) 먼저, '사전에 있으나 장면 값 없음'은 뒤에(값 대응 검토용 — 새 항목 후보가 아님)
    order = sorted(counts.items(), key=lambda kv: (kv[0][2].startswith("no_scene_value"), -kv[1]["count"], kv[0][2],
                                                   kv[0][0], kv[0][1]))
    n = 0
    for (lemma, tag, kind), c in order:
        if c["count"] < args.min_count:
            continue
        if not kind.startswith("no_scene_value") and not res.is_attribute_like(lemma):
            skipped[lemma] = skipped.get(lemma, 0) + c["count"]
            continue
        n += 1
        cands = res.candidates(lemma, tag) if not kind.startswith("no_scene_value") else []
        items.append({"id": f"P{n:04d}", "term": lemma, "tag": tag, "kind": kind, "why": c["why"], "count": c["count"],
                      "specs": c["specs"], "candidates": cands, "decision": _blank_decision()})
    doc = _header(res, args, sources, source_note=args.source)
    doc["skippedNonAttribute"] = {"note": "매퍼의 다른 규칙이 쓰는 말·불용 명사·기능어라 사전 후보에서 뺀 말(낱말: 횟수)",
                                  "words": dict(sorted(skipped.items(), key=lambda kv: (-kv[1], kv[0])))}
    doc["items"] = items
    return _write(doc, args.out, "collect")


# ── seed ────────────────────────────────────────────────────────────────────
def seed(args) -> Path:
    res = Resources(args.chain, args.variant_rules)
    data = json.loads(Path(args.words).read_text(encoding="utf-8"))
    words = data["words"] if isinstance(data, dict) else data
    items = []
    for n, w in enumerate(words, 1):
        if isinstance(w, str):
            w = {"term": w}
        term = w["term"]
        toks = [t for t in res.analyzer.tokens(term) if t.base_tag in CONTENT_TAGS]
        tag = toks[0].base_tag if len(toks) == 1 else "EOJEOL"
        lemma = toks[0].form if len(toks) == 1 else term
        direct, seen_d = [], set()
        for h in res.lexicon.hits(term):          # 1층 사전 직접 일치(Kiwi 형태 — '묵직하다' → 묵직)
            if h.entry.category not in SKIP_CATS and h.entry.key not in seen_d:
                seen_d.add(h.entry.key)
                direct.append(Resources._entry(h.entry))
        item = {"id": f"S{n:04d}", "term": term, "analysis": " ".join(f"{t.form}/{t.tag}" for t in res.analyzer.tokens(term)),
                "tag": tag, "kind": "seed", "inLexicon": direct,
                "candidates": res.candidates(lemma, tag) if not direct else [],
                "decision": _blank_decision()}
        for k in ("draftSuggestion", "context"):
            if k in w:
                item[k] = w[k]
        items.append(item)
    doc = _header(res, args, [{"kind": "word_list", "name": Path(args.words).name, "words": len(words)}],
                  source_note=args.source)
    doc["items"] = items
    return _write(doc, args.out, "seed")


def _header(res: Resources, args, sources: list[dict], source_note: str) -> dict:
    return {
        "format": FORMAT,
        "generatedBy": f"tools/lexicon_proposals.py {args.cmd}",
        "generatedOn": _now(),
        "source": source_note,
        "lexiconChain": res.chain,
        "variantRules": res.variants.info,
        "sources": sources,
        "privacy": "참여자 세션에서 만든 파일이면 참여자 데이터다. git에 올리지 않는다(AGENTS.md 6). 합성 자료로 만든 예시만 저장소에 둔다.",
        "howToReview": [
            "항목마다 decision.status를 approved 또는 rejected로 바꾼다. approved면 approvedBy(검토자)·approvedOn(YYYY-MM-DD)을 반드시 채운다.",
            "후보를 그대로 받으려면 decision.useCandidate에 candidates의 번호(0부터)를 적는다 — lemma·pos·category·value를 그 후보에서 가져오되 표제어는 term(또는 decision.lemma)이다.",
            "새 값을 직접 정하려면 decision.lemma(Kiwi 형태: 용언은 어간, -하다 형용사는 어근 XR)·pos·category·value를 적는다. value 키는 그 범주의 다른 항목과 같아야 한다(예: texture → {\"texture\": …}).",
            "참여자가 그 속성을 직접 말한 낱말만 승인한다. 감정어 → 색·모양처럼 말하지 않은 것을 채우는 대응은 승인하지 않는다(AGENTS.md 원칙 2).",
            "decision.ex에 그 표제어가 실제로 걸리는 합성 예문을 적으면 merge가 Kiwi로 확인한다(참여자 문장을 적지 않는다).",
            "후보(candidates)는 시스템이 고른 값이 아니라 검토를 돕는 이웃 낱말이다. jamo_neighbor는 거리 2까지라 다른 뜻의 낱말도 섞인다."
        ],
    }


def _write(doc: dict, out: str | None, stem: str) -> Path:
    if out:
        p = Path(out)
        if p.suffix != ".json":
            p = p / f"{stem}-{_now()}.proposals.json"
    else:
        p = DEFAULT_OUT / f"{stem}-{_now()}.proposals.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    if _in_git_tracked_area(p) and "synthetic" not in (doc.get("source") or ""):
        print(f"⚠ {p}는 git이 무시하지 않는 저장소 안입니다. 참여자 자료에서 만든 파일이면 저장소 밖이나 "
              f"chatbot/logs/ 아래로 옮기세요(AGENTS.md 6).", file=sys.stderr)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"proposals {len(doc.get('items', []))}개 → {p}")
    return p


# ── merge ───────────────────────────────────────────────────────────────────
class MergeError(ValueError):
    pass


def _bump(version: str) -> str:
    a, b, c = (int(x) for x in version.split("."))
    return f"{a}.{b + 1}.0"


def merge(args) -> Path:
    res = Resources(args.chain, args.variant_rules)
    base_name = args.chain[-1]
    base_path = shared("lexicon", base_name)
    base = json.loads(base_path.read_text(encoding="utf-8"))
    cats = res.lexicon.categories
    existing = {(e.category, e.lemma, e.pos) for e in res.lexicon.entries}
    new_entries: list[dict] = []
    errors: list[str] = []
    prov_files = []
    for pf in map(Path, args.proposals):
        doc = json.loads(pf.read_text(encoding="utf-8"))
        if doc.get("format") != FORMAT:
            raise MergeError(f"{pf.name}: format이 {FORMAT}이 아닙니다")
        prov_files.append({"name": pf.name, "sha256": _sha(pf), "generatedOn": doc.get("generatedOn"),
                           "source": doc.get("source")})
        for it in doc.get("items", []):
            d = it.get("decision") or {}
            if d.get("status") != "approved":
                continue
            where = f"{pf.name}:{it.get('id')}({it.get('term')})"
            if not d.get("approvedBy") or not d.get("approvedOn"):
                errors.append(f"{where}: approvedBy·approvedOn이 비었습니다")
                continue
            try:
                _dt.date.fromisoformat(d["approvedOn"])
            except ValueError:
                errors.append(f"{where}: approvedOn은 YYYY-MM-DD")
                continue
            e = {"lemma": d.get("lemma"), "pos": d.get("pos"), "category": d.get("category"), "value": d.get("value")}
            uc = d.get("useCandidate")
            if uc is not None:
                try:
                    c = it["candidates"][int(uc)]
                except (IndexError, ValueError, KeyError, TypeError):
                    errors.append(f"{where}: useCandidate {uc}번 후보가 없습니다")
                    continue
                e = {"lemma": d.get("lemma") or (it["term"] if it.get("tag") not in ("EOJEOL", "-") else None),
                     "pos": d.get("pos") or c["pos"], "category": d.get("category") or c["category"],
                     "value": d.get("value") or c["value"]}
            if not e["lemma"] or e["pos"] not in POS_OK or e["category"] not in cats or not isinstance(e["value"], dict) \
                    or not e["value"]:
                errors.append(f"{where}: lemma·pos({sorted(POS_OK)})·category(사전 범주)·value(빈 dict 아님)를 확인하세요 — {e}")
                continue
            if e["category"] in SKIP_CATS:
                errors.append(f"{where}: {e['category']} 범주는 이 도구로 더하지 않습니다(색은 scene_params colorTerms)")
                continue
            same = [x for x in res.lexicon.entries if x.category == e["category"]]
            keys = {k for x in same for k in x.value}
            if same and not set(e["value"]) <= keys:
                errors.append(f"{where}: value 키 {sorted(e['value'])}가 {e['category']} 범주의 키 {sorted(keys)}와 다릅니다")
                continue
            k = (e["category"], e["lemma"], e["pos"])
            if k in existing or any((x["category"], x["lemma"], x["pos"]) == k for x in new_entries):
                errors.append(f"{where}: 이미 있는 항목 {k}")
                continue
            ex = d.get("ex")
            if ex:
                hit = any(h.entry.lemma == e["lemma"] for h in _probe(res, e, ex))
                if not hit:
                    errors.append(f"{where}: 예문 '{ex}'에서 Kiwi가 '{e['lemma']}'를 내지 않습니다")
                    continue
            entry = {**e, "ex": ex or "", "src": f"review:{pf.name}#{it.get('id')}",
                     "review": {"approvedBy": d["approvedBy"], "approvedOn": d["approvedOn"], "note": d.get("note", ""),
                                "term": it.get("term"), "kind": it.get("kind")}}
            new_entries.append(entry)
    if errors:
        raise MergeError("승인 항목에 문제가 있어 합치지 않았습니다:\n  " + "\n  ".join(errors))
    if not new_entries:
        raise MergeError("approved 항목이 없습니다")
    version = args.version or _bump(base["lexiconVersion"])
    out = {**base, "lexiconVersion": version,
           "status": f"draft — {base_name} {base['lexiconVersion']} + 연구자 승인 {len(new_entries)}항목 ({_now()})",
           "reviewMerge": {"base": f"{base_name}@{base['lexiconVersion']}", "baseSha256": _sha(base_path),
                           "proposals": prov_files, "mergedOn": _now(), "added": len(new_entries),
                           "tool": "tools/lexicon_proposals.py merge"},
           "entries": base["entries"] + new_entries}
    p = Path(args.out) if args.out else DEFAULT_OUT / f"{Path(base_name).stem}.{version}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(new_entries)}항목을 더한 {base_name} {version} → {p}")
    print("매퍼가 이 파일을 쓰게 하려면 shared/lexicon/에 두고 config [mapping] ext_lexicon에 파일 이름을 적는다(검토 후).")
    return p


def _probe(res: Resources, e: dict, ex: str):
    from ifs_chatbot.lexicon import Lexicon
    cat = res.lexicon.categories.get(e["category"], {})
    data = {"lexiconId": "probe", "lexiconVersion": "0", "categories": {e["category"]: cat},
            "entries": [{**{k: e[k] for k in ("lemma", "pos", "category", "value")}, "ex": ex}]}
    return Lexicon(Path("probe.json"), res.analyzer, data=data).hits(ex)


# ── CLI ─────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--chain", nargs="+", default=DEFAULT_CHAIN,
                    help="합쳐 볼 1층 사전 파일들(shared/lexicon/ 아래, 차례대로). merge는 마지막 파일의 새 버전을 만든다")
    ap.add_argument("--variant-rules", default="variant_rules.v0.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect", help="장면 파일·세션 기록·합성 코퍼스에서 미대응 낱말을 모아 proposals를 쓴다")
    c.add_argument("paths", nargs="*", help="장면 파일 또는 폴더(하위 *.json을 모두 읽음)")
    c.add_argument("--corpus", nargs="*", default=[], help="합성 코퍼스(dev.json 형식) 또는 문자열 목록 JSON — 매퍼 v2로 spec을 만든다")
    c.add_argument("--min-count", type=int, default=1)
    c.add_argument("--source", default="session data — 참여자 데이터일 수 있음, git에 올리지 않음")
    c.add_argument("--out", help=f"파일(.json) 또는 폴더. 기본 {DEFAULT_OUT}")
    s = sub.add_parser("seed", help="낱말 목록으로 proposals를 쓴다(합성 후보 검토용)")
    s.add_argument("words")
    s.add_argument("--source", default="synthetic, 연구자 검토 전")
    s.add_argument("--out")
    m = sub.add_parser("merge", help="approved 항목만 새 사전 버전 파일로 합친다")
    m.add_argument("proposals", nargs="+")
    m.add_argument("--version", help="새 lexiconVersion(기본: 부 버전 +1)")
    m.add_argument("--out", help=f"새 사전 파일 경로. 기본 {DEFAULT_OUT}/<사전>.<버전>.json")
    args = ap.parse_args(argv)
    try:
        {"collect": collect, "seed": seed, "merge": merge}[args.cmd](args)
    except MergeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
