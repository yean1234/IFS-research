"""G84 실제 흐름 확인: 형태 사전 0.3.0(낱말을 더함)으로 G82 점검에서 LLM에 기대던 문장이 규칙만으로 끝까지 가는지(합성 대사만).

G83 점검 스크립트(docs/validation/run-g83-g82-on/run_g83_e2e.py — G82 점검 스크립트에 단추 크기·G83 기록 칸을 더한 것)를
그대로 불러 쓴다. 결과는 이 폴더에 쓴다(--out 기본값만 바꿈). 서버는 experiment.toml 사본(로그 폴더만 저장소 밖 임시 위치)으로
--port 8011에 따로 띄운 뒤 돌린다.

  python run_g84_e2e.py --base http://127.0.0.1:8011 --logs <서버 log_dir> --raw <임시 폴더> --cases cases.json --sid-prefix SYN-G84
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "run-g83-g82-on"))
import run_g83_e2e as g83  # noqa: E402

if __name__ == "__main__":
    if not any(x == "--out" or x.startswith("--out=") for x in sys.argv[1:]):
        sys.argv += ["--out", str(HERE)]
    g83.base.main()
