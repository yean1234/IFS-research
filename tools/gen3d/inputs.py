"""입력 문장 모으기 → 저장소 밖 sentences.json + 문장 id ↔ 원문 대응표.

  python tools/gen3d/inputs.py --answers <notion answers.json> [--max 20] --run <이름>
  python tools/gen3d/inputs.py --dev 10 --run <이름>

- answers.json 형식: [{"id", "text", "source_title", "kind", ...}]. kind가 "실제 응답"인 것을 먼저, 모자라면 "연구자 예시".
- --dev N: chatbot/tests/fixtures/imagery_corpus/dev.json(합성)의 앞 N개. replies를 줄바꿈으로 잇는다
  (eval/fidelity.py와 같은 방식. 실제 면담의 확정 텍스트는 컨트롤러가 버린 답을 빼므로 조금 다를 수 있음).
  heldout.json은 읽지 않는다.
- 출력은 OUT_ROOT/<run>/inputs/ 아래(저장소 밖, 원칙 6). 비교 시트에는 id만 쓰고 원문은 이 대응표에만 둔다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CHATBOT, OUT_ROOT, assert_outside_repo, read_json, write_json  # noqa: E402

KIND_ORDER = ("실제 응답", "연구자 예시")


def from_answers(path: Path, max_n: int) -> list[dict]:
    rows = read_json(path)
    out: list[dict] = []
    for kind in KIND_ORDER:
        for r in rows:
            if r.get("kind") == kind and (r.get("text") or "").strip():
                out.append({"id": str(r["id"]), "text": r["text"].strip(), "kind": kind,
                            "source": r.get("source_title")})
                if len(out) >= max_n:
                    return out
    return out


def from_dev(n: int) -> list[dict]:
    corpus = read_json(CHATBOT / "tests" / "fixtures" / "imagery_corpus" / "dev.json")
    out = []
    for it in corpus["items"][:n]:
        text = "\n".join(v.strip() for v in it["replies"].values() if isinstance(v, str) and v.strip())
        out.append({"id": it["id"], "text": text, "kind": "합성(dev.json)", "source": corpus.get("corpusId")})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", type=Path)
    ap.add_argument("--max", type=int, default=20)
    ap.add_argument("--dev", type=int, default=0)
    ap.add_argument("--run", required=True)
    a = ap.parse_args(argv)
    rows = from_answers(a.answers, a.max) if a.answers else from_dev(a.dev or 10)
    run_dir = assert_outside_repo(OUT_ROOT / a.run)
    write_json(run_dir / "inputs" / "sentences.json", rows)
    # 사람이 읽는 대응표(원문 포함) — 저장소 밖에만 둔다.
    table = ["| id | kind | text |", "| --- | --- | --- |"]
    table += [f"| {r['id']} | {r['kind']} | {r['text'].replace(chr(10), ' / ')} |" for r in rows]
    (run_dir / "inputs" / "id_text_table.md").write_text("\n".join(table) + "\n", encoding="utf-8")
    print(f"{len(rows)}문장 → {run_dir / 'inputs'}")


if __name__ == "__main__":
    main()
