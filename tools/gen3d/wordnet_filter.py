"""G73-a WordNet 거르개: 대역 사전에서 온 영어 명사가 프롬프트에 들어가도 되는지(사전·규칙만, 모델 없음).

판정(shared/lexicon/resay_prompt_filter.v0.json wordnet):
- block: 상위어 닫힘에 사람·동물·생물·몸 부위·사람 닮은 사물·메시로 안 되는 범주가 있으면 → 생성 전체를 막는다.
- drop: physical_entity 아래가 아니거나 감정·심리 범주 → 그 대역어만 버린다.
- unjudgeable: WordNet이 없거나(nltk·데이터 없음) 그 낱말이 WordNet에 없음 → 버린다(fail closed).
- pass: 위에 걸리지 않은 물리적 사물.

nltk는 선택 의존성이다. 데이터를 내려받지 않는다(nltk.download를 부르지 않음, 외부 전송 없음). 없으면 available = False이고
모든 판정이 unjudgeable이라 대역 사전 낱말은 프롬프트에 들어가지 않는다. 판과 데이터 sha256을 info()에 남긴다.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def _file_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def data_sha256(p: Path) -> str | None:
    """WordNet 데이터 내용 해시. 압축 파일이면 파일 바이트, 폴더면 안의 파일을 상대 경로(posix) 차례로 정렬해
    (경로, 파일 sha256)를 이어 해시한다(CP13 지적 3). 숨은 파일('.'로 시작: .DS_Store 등)은 내용이 아니라 뺀다.
    같은 내용이면 설치 위치·파일 시각과 상관없이 같은 값, 파일 하나라도 다르면 다른 값."""
    p = Path(p)
    if p.is_file():
        return _file_sha256(p)
    if not p.is_dir():
        return None
    h = hashlib.sha256()
    h.update(b"dir-v1\n")
    files = sorted((f.relative_to(p).as_posix(), f) for f in p.rglob("*")
                   if f.is_file() and not any(part.startswith(".") for part in f.relative_to(p).parts))
    for rel, f in files:
        h.update(rel.encode("utf-8") + b"\0" + _file_sha256(f).encode("ascii") + b"\n")
    return h.hexdigest()


class NltkWordNet:
    """nltk WordNet 백엔드. 데이터가 없으면 LookupError(내려받지 않음)."""
    name = "nltk"

    def __init__(self):
        import nltk
        from nltk.corpus import wordnet as wn

        wn.ensure_loaded()                       # 데이터가 없으면 LookupError. 내려받기는 하지 않는다
        self.wn = wn
        self.nltk_version = nltk.__version__
        self.version = wn.get_version()
        self.data_path: str | None = None
        self.data_sha256: str | None = None
        for res in ("corpora/wordnet.zip", "corpora/wordnet"):
            try:
                p = Path(str(nltk.data.find(res)))
            except LookupError:
                continue
            self.data_path = p.name
            self.data_sha256 = data_sha256(p)
            break

    def noun_senses(self, phrase: str) -> list[tuple[str, frozenset]]:
        lemma = phrase.strip().lower().replace(" ", "_").replace("-", "_")
        out = []
        for s in self.wn.synsets(lemma, pos=self.wn.NOUN):
            clos = {h.name() for h in s.closure(lambda x: x.hypernyms() + x.instance_hypernyms())}
            out.append((s.name(), frozenset(clos | {s.name()})))
        return out

    def info(self) -> dict:
        return {"backend": self.name, "nltkVersion": self.nltk_version, "wordnetVersion": self.version,
                "data": self.data_path, "dataSha256": self.data_sha256}


class TableWordNet:
    """시험용 합성 백엔드: {영어 낱말: [[synset 이름, [상위어 …]], …]}(뜻 차례 = WordNet 빈도 차례 흉내)."""
    name = "table"

    def __init__(self, table: dict, version: str = "synthetic-test"):
        self.table = table
        self.version = version

    def noun_senses(self, phrase: str) -> list[tuple[str, frozenset]]:
        key = phrase.strip().lower()
        return [(n, frozenset(set(h) | {n})) for n, h in self.table.get(key, [])]

    def info(self) -> dict:
        return {"backend": self.name, "wordnetVersion": self.version, "dataSha256": None}


class WordNetFilter:
    def __init__(self, filt: dict, backend=None, unavailable_reason: str | None = None):
        self.cfg = filt["wordnet"]
        self.backend = backend
        self.unavailable_reason = unavailable_reason if backend is None else None
        self.block = {cat: frozenset(names) for cat, names in self.cfg["block"].items()}
        self.drop = frozenset(n for names in self.cfg["drop"].values() for n in names)
        self.physical = self.cfg["requirePhysical"]
        self.scope = self.cfg["senseScope"]
        if self.scope not in ("dominant", "all"):
            raise ValueError(f"senseScope는 dominant | all: {self.scope!r}")

    @classmethod
    def auto(cls, filt: dict) -> "WordNetFilter":
        """nltk WordNet이 있으면 쓰고, 없으면 쓸 수 없는 거르개(모든 판정 unjudgeable)."""
        try:
            return cls(filt, NltkWordNet())
        except ImportError:
            return cls(filt, None, "nltk_not_installed")
        except (LookupError, OSError):
            return cls(filt, None, "wordnet_data_missing")

    @property
    def available(self) -> bool:
        return self.backend is not None

    def info(self) -> dict:
        if self.backend is None:
            return {"available": False, "reason": self.unavailable_reason, "senseScope": self.scope}
        return {"available": True, "senseScope": self.scope, **self.backend.info()}

    def judge(self, en: str) -> dict:
        if self.backend is None:
            return {"en": en, "verdict": "unjudgeable", "reason": self.unavailable_reason}
        senses = self.backend.noun_senses(en)
        if not senses:
            return {"en": en, "verdict": "unjudgeable", "reason": "not_in_wordnet"}
        scope = senses[:1] if self.scope == "dominant" else senses
        for name, clos in scope:
            for cat, names in self.block.items():
                hit = sorted(clos & names)
                if hit:
                    return {"en": en, "verdict": "block", "reason": f"{cat}:{hit[0]}", "synset": name,
                            "senses": len(senses)}
        name, clos = senses[0]
        if self.scope == "dominant":
            physical, psych = self.physical in clos, bool(clos & self.drop)
        else:
            physical = any(self.physical in c for _, c in senses)
            psych = all(bool(c & self.drop) for _, c in senses)
        if psych:
            return {"en": en, "verdict": "drop", "reason": "psychological", "synset": name, "senses": len(senses)}
        if not physical:
            return {"en": en, "verdict": "drop", "reason": "non_physical", "synset": name, "senses": len(senses)}
        return {"en": en, "verdict": "pass", "reason": None, "synset": name, "senses": len(senses)}
