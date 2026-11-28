"""G83 실제 흐름 재확인: G82를 켠 experiment.toml 사본으로 a–d 수정이 화면·기록에 나타나는지(합성 대사만).

G82 점검 스크립트(docs/validation/run-g82-end-to-end/run_g82_e2e.py)를 그대로 쓰고 두 곳만 덧붙인다.
  - 화면 정보(info)에 [그 말이 아니에요]·그림 단추 [이걸로 할게요]의 크기(c)와 조절 화면 안내 줄(a)을 더함
  - results.json 간추림(compact)에 G83 기록 칸(basisShown·candidateExposed·afterNone.gate·shapeLlmBasisShown)을 더함
서버는 experiment.toml 사본(로그 폴더만 저장소 밖 임시 위치)으로 따로 띄운 뒤 돌린다. 사용법은 run_g82_e2e.py와 같다.

  python run_g83_e2e.py --base http://127.0.0.1:8011 --logs <서버 log_dir> --raw <임시 폴더> --cases cases.json --sid-prefix SYN-G83
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "run-g82-end-to-end"))
import run_g82_e2e as base  # noqa: E402

_OLD = "scrollH: document.documentElement.scrollHeight };"
assert _OLD in base.HELPERS
base.HELPERS = base.HELPERS.replace(_OLD, """scrollH: document.documentElement.scrollHeight,
             buttons: (() => { const R = (e) => { if (!e) return null; const r = e.getBoundingClientRect();
                                 return { w: Math.round(r.width), h: Math.round(r.height) }; };
                               return { wrong: R(document.querySelector('button[data-fkey="img:basis-wrong"]')),
                                        choose: R(document.querySelector('.pick-card .pick')) }; })(),
             genNote: (() => { const n = document.querySelector('.none-gen-note'); return n ? n.textContent : null; })() };""")

_compact = base.compact


def compact(sel):
    out = _compact(sel)
    if not out:
        return out
    gen = (sel or {}).get("generation") or {}
    sl = gen.get("shapeLlm") or {}
    an = gen.get("afterNone") or {}
    if out.get("shapeLlm") is not None:
        out["shapeLlm"].update(candidateExposed=sl.get("candidateExposed"), basisShown=sl.get("basisShown"))
    if out.get("afterNone") is not None:
        out["afterNone"].update(gateWhenBlocked=an.get("gate"), shapeLlmBasisShown=an.get("shapeLlmBasisShown"))
    return out


base.compact = compact

if __name__ == "__main__":
    base.main()
