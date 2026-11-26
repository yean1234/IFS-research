"""형태 변이 규칙층(0.5층) — 사전에 직접 없는 낱말의 뿌리를 결정적 규칙으로 구한다(G61 ②).

규칙 표: shared/lexicon/variant_rules.v0.json. 학습 모델·임베딩·외부 자원 없음. 같은 입력은 언제나 같은 결과다.
쓰는 곳: 매퍼 v2(scene_builder_v2.py)가 [mapping] variant_rules를 켰을 때만.

규칙은 정해진 순서로만 쌓는다(한 번씩): 어미 떼기 → 파생 접사 떼기 → 겹친 꼴 줄이기 → 모음 교체 / 자음 교체 / 둘 다.
뿌리가 사전에 있을 때만 그 항목을 돌려준다. 강도(큰말·작은말·센소리·-스름)는 값을 바꾸지 않고 grade로만 기록한다.
"""
from __future__ import annotations

import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .lexicon import LexEntry

_BASE, _LAST = 0xAC00, 0xD7A3
ONSETS = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
VOWELS = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"


def _split(ch: str) -> tuple[int, int, int] | None:
    c = ord(ch)
    if not _BASE <= c <= _LAST:
        return None
    i = c - _BASE
    return i // 588, (i % 588) // 28, i % 28


def _join(lead: int, vowel: int, tail: int) -> str:
    return chr(_BASE + lead * 588 + vowel * 28 + tail)


@dataclass(frozen=True)
class VariantMatch:
    entries: tuple[LexEntry, ...]   # 뿌리가 걸린 사전 항목(같은 꼴의 여러 범주 — 직접 일치가 여러 범주를 내는 것과 같다)
    root: str                       # 사전에서 찾은 꼴(표제어 또는 이형)
    surface: str                    # 규칙에 넣은 원래 표면형(토큰 형태 또는 어절)
    rules: tuple[str, ...]          # 적용한 규칙(순서대로)
    grades: tuple[str, ...]         # 강도 기록(값은 바꾸지 않음)

    def tag(self) -> str:
        """provenance rule 앞머리. 스펙 2.2(구조 필드가 없음)에서도 같은 정보를 남기기 위한 문자열 꼴."""
        g = f";grade={','.join(self.grades)}" if self.grades else ""
        return f"variant({'>'.join(self.rules)};surface={self.surface};root={self.root}{g})"

    def record(self) -> dict:
        """스펙 2.3 provenance.variant 구조."""
        return {"rules": list(self.rules), "surface": self.surface, "root": self.root, "grade": list(self.grades)}


def parse_tag(rule: str) -> dict | None:
    """provenance rule 문자열의 'variant(…)' 머리를 구조로 되돌린다(2.3 provenance.variant). 없으면 None."""
    if not rule.startswith("variant("):
        return None
    head = rule[len("variant("):rule.index(")")]
    parts = head.split(";")
    out = {"rules": parts[0].split(">"), "surface": "", "root": "", "grade": []}
    for p in parts[1:]:
        k, _, v = p.partition("=")
        if k == "grade":
            out["grade"] = v.split(",") if v else []
        elif k in ("surface", "root"):
            out[k] = v
    return out


class VariantRules:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        d = json.loads(self.path.read_text(encoding="utf-8"))
        self.data = d
        self.info = f"{d['lexiconId']}@{d['lexiconVersion']}"
        self.source_tags = frozenset(d["sourceTags"])
        self.min_syll = int(d["minRootSyllables"])
        self.max_comb = int(d["maxCombinations"])
        self.root_forms: list[str] = list(d["rootForms"])
        acc = d["acceptAlternationTargets"]
        self.alt_pos = frozenset(acc["pos"])
        self.alt_verb_endings = tuple(acc["derivedVerbEndings"])
        self.alt_categories = frozenset(acc["categories"])
        r = d["rules"]
        self.endings = sorted(r["ending"]["endings"], key=lambda s: (-len(s), s))
        self.ending_suffix: dict[str, str] = r["ending"]["derivedSuffix"]
        self.suffixes: list[tuple[str, str | None]] = sorted(((s["form"], s.get("grade")) for s in r["suffix"]["suffixes"]),
                                                             key=lambda x: (-len(x[0]), x[0]))
        self.suffix_grade = dict(self.suffixes)
        vg = r["ideophone_vowel"]["grade"]
        self.v_grade_eum, self.v_grade_yang = vg["surfaceIsEum"], vg["surfaceIsYang"]
        # 모음 → (양성→음성) 대상, (음성→양성) 대상
        self.to_eum: dict[int, list[int]] = {}
        self.to_yang: dict[int, list[int]] = {}
        for yang, eum in r["ideophone_vowel"]["pairs"]:
            y, e = VOWELS.index(yang), VOWELS.index(eum)
            self.to_eum.setdefault(y, []).append(e)
            self.to_yang.setdefault(e, []).append(y)
        cg = r["ideophone_consonant"]["grade"]
        self.c_grade_strong, self.c_grade_weak = cg["surfaceStronger"], cg["surfaceWeaker"]
        self.series: dict[int, tuple[list[int], int]] = {}       # 초성 → (계열 초성 목록, 등급 0 예사·1 거센·2 된)
        for ser in r["ideophone_consonant"]["series"]:
            idx = [ONSETS.index(x) for x in ser]
            grades = [0, 2] if len(ser) == 2 else [0, 1, 2]      # ㅅ·ㅆ = 예사·된
            for k, o in enumerate(idx):
                self.series[o] = (idx, grades[k])
        self._grade_of = {o: g for o, (idx, g) in self.series.items()}
        self.stop = frozenset(d["stoplist"]["forms"])
        self.combined = bool(r.get("combined", {}).get("enabled", False))

    # ── 줄기 만들기 ──────────────────────────────────────────────────────────
    def _stems(self, form: str, tag: str, next_form: str | None) -> list[tuple[str, tuple[str, ...], tuple[str, ...]]]:
        """(줄기, 규칙, grade) 목록. 규칙이 적은 것부터. 어미 → 접사 → 겹친 꼴 순으로 한 번씩."""
        # Kiwi가 파생 접사를 다음 형태소로 뗀 경우('꼼틀/NNG + 거리/XSV')는 처음 줄기에 그 접사 규칙을 단다
        if next_form is not None and next_form in self.suffix_grade:
            g0 = self.suffix_grade[next_form]
            out: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [(form, (f"suffix:{next_form}",), (g0,) if g0 else ())]
        else:
            out = [(form, (), ())]
        # 어미: 묶인 꼴(NNG·UN·어절)에서만
        if tag in ("NNG", "UN", "EOJEOL"):
            for end in self.endings:
                if form.endswith(end) and len(form) - len(end) >= self.min_syll:
                    suf = self.ending_suffix.get(end)
                    rules = ("ending",) + ((f"suffix:{suf}",) if suf else ())
                    g = self.suffix_grade.get(suf) if suf else None
                    out.append((form[:-len(end)], rules, (g,) if g else ()))
                    break
        # 파생 접사: 끝에 붙은 것(묶인 꼴) 또는 Kiwi가 다음 형태소로 뗀 것
        more = []
        for stem, rules, grades in out:
            if any(r.startswith("suffix:") for r in rules):
                continue
            for suf, g in self.suffixes:
                if stem.endswith(suf) and len(stem) - len(suf) >= self.min_syll:
                    more.append((stem[:-len(suf)], rules + (f"suffix:{suf}",), grades + ((g,) if g else ())))
                    break
        out += more
        # 겹친 꼴
        more = []
        for stem, rules, grades in out:
            n = len(stem)
            if n >= 2 * self.min_syll and n % 2 == 0 and stem[:n // 2] == stem[n // 2:]:
                more.append((stem[:n // 2], rules + ("reduplication",), grades))
        out += more
        seen, uniq = set(), []
        for x in sorted(out, key=lambda x: len(x[1])):
            if x[0] not in seen:
                seen.add(x[0])
                uniq.append(x)
        return uniq

    # ── 교체 ─────────────────────────────────────────────────────────────────
    def _vowel_alts(self, stem: str) -> list[tuple[str, str]]:
        """(바꾼 꼴, grade). 같은 방향으로만, 바꾸는 음절은 일부여도 된다."""
        sy = [_split(c) for c in stem]
        if any(s is None for s in sy):
            return []
        out = []
        for table, grade in ((self.to_eum, self.v_grade_yang), (self.to_yang, self.v_grade_eum)):
            # to_eum: 말한 꼴이 양성 → 사전 쪽은 음성 → 말한 꼴은 작은말(smaller)
            opts = [[s[1]] + table.get(s[1], []) for s in sy]
            for combo in itertools.islice(itertools.product(*opts), self.max_comb):
                if all(v == s[1] for v, s in zip(combo, sy)):
                    continue
                out.append(("".join(_join(s[0], v, s[2]) for s, v in zip(sy, combo)), grade))
        return out

    def _consonant_alts(self, stem: str) -> list[tuple[str, str]]:
        sy = [_split(c) for c in stem]
        if any(s is None for s in sy):
            return []
        out = []
        for direction in ("down", "up"):
            opts = []
            for s in sy:
                lead = s[0]
                if lead not in self.series:
                    opts.append([lead])
                    continue
                idx, g = self.series[lead]
                if direction == "down":
                    opts.append([lead] + [o for o in idx if self._grade_of[o] < g])
                else:
                    opts.append([lead] + [o for o in idx if self._grade_of[o] > g])
            # 말한 꼴의 초성을 여린 쪽으로 바꿔 사전을 찾음(down) → 말한 꼴이 더 센 소리(stronger)
            grade = self.c_grade_strong if direction == "down" else self.c_grade_weak
            for combo in itertools.islice(itertools.product(*opts), self.max_comb):
                if all(o == s[0] for o, s in zip(combo, sy)):
                    continue
                out.append(("".join(_join(o, s[1], s[2]) for s, o in zip(sy, combo)), grade))
        return out

    # ── 찾기 ─────────────────────────────────────────────────────────────────
    def _accept_alternation(self, e: LexEntry) -> bool:
        return e.category in self.alt_categories and (
            e.pos in self.alt_pos or (e.pos == "VV" and e.lemma.endswith(self.alt_verb_endings)))

    def resolve(self, form: str, tag: str, next_form: str | None,
                lookup: Callable[[str], Iterable[LexEntry]], accept: Callable[[LexEntry], bool]) -> VariantMatch | None:
        """form(토큰 형태 또는 어절 표면형)의 뿌리를 규칙으로 구해 사전 항목을 돌려준다. tag는 Kiwi 기본 품사 또는 EOJEOL.
        lookup(꼴) → 그 꼴의 사전 항목, accept(항목) → 이 층에서 받을 범주인지. 아무 규칙도 쓰지 않은 일치는 돌려주지 않는다
        (직접 일치는 1층 사전이 맡는다)."""
        if tag != "EOJEOL" and tag not in self.source_tags:
            return None
        stems = self._stems(form, tag, next_form)
        if any(s in self.stop for s, _, _ in stems):
            return None
        # 단계: 교체 없음 → 모음 → 자음 (→ 둘 다, 꺼 둠). 앞 단계에서 어느 줄기라도 걸리면 뒤 단계로 가지 않는다
        # ('번쩍번쩍' → 겹친 꼴 줄이기만으로 번쩍이(사전)에 닿으면 모음 교체 '반짝반짝'까지 가지 않음).
        # 한 단계 안에서는 규칙이 적은 줄기부터 보고, 처음 걸린 줄기에서 (범주, 값)이 서로 다른 항목이 걸리면 대응하지 않는다
        stage_names: list[str | None] = [None, "ideophone_vowel", "ideophone_consonant"]
        if self.combined:
            stage_names.append("ideophone_vowel+consonant")
        for rule in stage_names:
            for stem, rules, grades in stems:
                if len(stem) < self.min_syll:
                    continue
                if tag == "NNG" and not any(r in ("reduplication", "ending") or r.startswith("suffix:") for r in rules):
                    continue                # 보통 명사(겹친 꼴·묶인 어미·접사가 없음)에는 걸지 않는다
                if rule is None and not rules:
                    continue                # 규칙 없이 같은 꼴 — 직접 일치(1층) 몫
                # 교체는 의태어 꼴에만: 어근·부사(XR·MAG)이거나 겹친 꼴·파생 접사·어미를 뗀 꼴. 용언 원형('말리다')에는 걸지 않는다
                if rule is not None and not (tag in ("XR", "MAG") or rules):
                    continue
                if rule is None:
                    variants: list[tuple[str, tuple[str, ...]]] = [(stem, ())]
                elif rule == "ideophone_vowel":
                    variants = [(a, (g,)) for a, g in self._vowel_alts(stem)]
                elif rule == "ideophone_consonant":
                    variants = [(a, (g,)) for a, g in self._consonant_alts(stem)]
                else:
                    variants = []
                    for a, g in self._vowel_alts(stem):
                        variants += [(b, (g, h)) for b, h in self._consonant_alts(a)]
                    variants = variants[: self.max_comb]
                found: list[tuple[str, tuple[LexEntry, ...], tuple[str, ...]]] = []
                # 뗀 접사가 -거리·-이면 그 꼴을 먼저 찾는다('빤짝여요' → 반짝이)
                sufs = [r.split(":", 1)[1] for r in rules if r.startswith("suffix:")]
                forms = sorted(self.root_forms, key=lambda t: 0 if any(t == "{root}" + s for s in sufs) else 1)
                for base, g in variants:
                    for tmpl in forms:
                        cand = tmpl.replace("{root}", base)
                        ents = tuple(e for e in lookup(cand) if accept(e) and (rule is None or self._accept_alternation(e)))
                        if ents:
                            found.append((cand, ents, g))
                            break
                if not found:
                    continue
                kinds = {frozenset((e.category, json.dumps(e.value, sort_keys=True, ensure_ascii=False)) for e in ents)
                         for _, ents, _ in found}
                if len(kinds) != 1:
                    return None             # 동률 후보가 서로 다르면 대응하지 않는다
                cand, ents, g = found[0]
                all_rules = rules + ((rule,) if rule else ())
                return VariantMatch(entries=ents, root=cand, surface=form, rules=all_rules,
                                    grades=tuple(x for x in grades + g if x))
        return None
