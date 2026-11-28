"""G84 요약 시트: G82 점검의 make_summary.py(docs/validation/run-g82-end-to-end/)를 그대로 돌리고 부제의 설정 이름만 바꾼다.

  python make_summary.py --raw <임시 폴더> [--per-sheet 4] [--title "G84 실제 흐름 확인(형태 사전 0.3.0)"]
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "run-g82-end-to-end" / "make_summary.py"
src = SRC.read_text(encoding="utf-8")
assert "experiment-g82 설정" in src
src = src.replace("experiment-g82 설정", "experiment.toml 사본(G84, 형태 사전 0.3.0)")
exec(compile(src, str(SRC), "exec"), {"__name__": "__main__", "__file__": str(HERE / "make_summary.py")})
