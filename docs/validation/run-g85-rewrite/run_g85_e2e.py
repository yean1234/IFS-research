"""G85 실제 흐름 점검: experiment-g85.toml 사본으로 띄운 서버에서 참여자 화면을 끝까지(합성 대사만).

G82 점검 스크립트(docs/validation/run-g82-end-to-end/run_g82_e2e.py)의 소스를 불러 몇 곳만 바꿔 돌린다(그 파일은 고치지 않음).
  - 화면 정보(info): 근거 줄은 G82 줄(shape-basis)과 G85 줄(rewrite-basis) 둘 다 보고, 덧붙임 줄(rewrite-added)·메시 재시도 줄
    (mesh-retry)·중립 형태 안내(llmRewriteNeutral)를 더함
  - 고른 그림의 메시가 관문에 막혀 고르기 화면으로 돌아오면(G85 on_none_mesh_retry) 그 화면을 찍고 남은 그림 맨 앞을 골라 한 번 더
  - results.json 간추림에 generation.promptRoute·rewrite·meshRetry·afterNone.promptRoute를 더함

  python run_g85_e2e.py --base http://127.0.0.1:8011 --logs <서버 log_dir> --raw <임시 폴더> --cases cases_e2e.json --sid-prefix SYN-G85
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "run-g82-end-to-end" / "run_g82_e2e.py"
src = SRC.read_text(encoding="utf-8")


def sub(a, b):
    global src
    assert src.count(a) == 1, a[:80]
    src = src.replace(a, b)


sub("""    const basisEl = document.querySelector('[data-fkey="shape-basis"]');""",
    """    const basisEl = document.querySelector('[data-fkey="shape-basis"],[data-fkey="rewrite-basis"]');
    const addedEl = document.querySelector('[data-fkey="rewrite-added"]');
    const retryEl = document.querySelector('[data-fkey="mesh-retry"]');""")
sub("""             llmShapeBasis: v.llmShapeBasis || null,""",
    """             llmShapeBasis: v.llmShapeBasis || null, llmRewriteBasis: v.llmRewriteBasis || null,
             llmRewriteNeutral: v.llmRewriteNeutral || null, addedLine: addedEl ? addedEl.textContent : null,
             meshRetryLine: retryEl ? retryEl.textContent : null,""")
sub("""                                st = await wait_generating(st, cid, "mesh", r, sid)
                                r["timings"]["pickToNextScreenS"] = round(time.time() - t_pick, 1)
                                r["steps"].append({"at": "after_pick", **st})""",
    """                                st = await wait_generating(st, cid, "mesh", r, sid)
                                r["timings"]["pickToNextScreenS"] = round(time.time() - t_pick, 1)
                                r["steps"].append({"at": "after_pick", **st})
                                if st["stage"] == "picking":            # (G85) 메시 관문 → 남은 그림으로 한 번 돌아옴
                                    r["shots"]["b3"] = await shot(f"{cid}_b3_mesh_retry", r, sid)
                                    r["meshRetryLine"] = st.get("meshRetryLine")
                                    nxt = st["imagePick"]["images"][0]["position"]
                                    r["retryPickedPosition"] = nxt
                                    await ev(f"__g82.clickFkey('img:{nxt}')")
                                    st = await wait_generating(st, cid, "mesh2", r, sid)
                                    r["steps"].append({"at": "after_retry_pick", **st})""")
sub("""                            name = f"{cid}_b_images_basis" if st.get("basisShown") else f"{cid}_b_images\"""",
    """                            name = f"{cid}_b_images_basis" if st.get("basisShown") else (
                                f"{cid}_b_images_neutral" if st.get("llmRewriteNeutral") else f"{cid}_b_images")""")
sub('prof = tempfile.mkdtemp(prefix="ifs-g82-cdp-")', 'prof = tempfile.mkdtemp(prefix="ifs-g85-cdp-")')
sub('resp_path = out / "results.json"', 'resp_path = out / "e2e_results.json"')     # 오프라인 점검 결과와 이름이 겹치지 않게

ns = {"__name__": "run_g82_e2e_g85", "__file__": str(HERE / "run_g85_e2e.py")}   # 기본 --out = 이 폴더
exec(compile(src, str(SRC), "exec"), ns)
_compact = ns["compact"]


def compact(sel):
    out = _compact(sel)
    if not out:
        return out
    gen = (sel or {}).get("generation") or {}
    rw = gen.get("rewrite") or {}
    an = gen.get("afterNone") or {}
    out["promptRoute"] = gen.get("promptRoute")
    out["rewrite"] = None if not rw else {k: rw.get(k) for k in (
        "route", "routeReason", "called", "status", "outcome", "adopted", "elements", "addedCount", "rejectReasons", "forbidden",
        "rawText", "assembledPrompt", "negativePrompt", "neutralForm", "basisShown", "exposed", "addedLineShown",
        "neutralLineShown", "imageChosen", "candidateExposed", "candidateChosen", "rejected", "promptVersion", "seed",
        "temperature", "wordnet", "model")}
    out["meshRetry"] = gen.get("meshRetry")
    if out.get("afterNone") is not None:
        out["afterNone"].update(promptRoute=an.get("promptRoute"), rewriteUsed=an.get("rewriteUsed"),
                                neutralUsed=an.get("neutralUsed"), rewriteBasisShown=an.get("rewriteBasisShown"),
                                meshAttempts=an.get("meshAttempts"), gateWhenBlocked=an.get("gate"),
                                addedCount=(an.get("prompt") or {}).get("rewriteAddedCount"))
    return out


ns["compact"] = compact

if __name__ == "__main__":
    sys.argv[0] = str(HERE / "run_g85_e2e.py")
    ns["main"]()
