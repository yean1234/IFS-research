"""spec 폴더의 <id>.<매핑>.json에서 값이 있는 슬롯·근거 낱말·_unmapped·_negated·_inferred를 한눈에 본다. 사용: python spec_slots.py <spec 폴더> v2"""
import json, sys, glob
from pathlib import Path
def flat(spec):
    out = {}
    for sec in ("form", "material", "layout", "motion", "body"):
        for k, v in (spec.get(sec) or {}).items():
            out[f"{sec}.{k}"] = v
    return out
for f in sorted(glob.glob(sys.argv[1] + "/*." + sys.argv[2] + ".json")):
    s = json.load(open(f, encoding="utf-8"))
    print("=====", Path(f).name, s["meta"]["specVersion"])
    prov = s.get("_provenance", {})
    for k, v in flat(s).items():
        if v is not None:
            tr = [(p.get("trigger"), p.get("source")) for p in (prov.get(k) or [])]
            print(f"   {k:24} = {json.dumps(v, ensure_ascii=False)[:60]:60} <- {tr}")
    for u in s.get("_unmapped", []):
        print(f"   unmapped {u['lemma']}/{u['category']} {u.get('reason')} {json.dumps(u.get('value'), ensure_ascii=False)[:60]}")
    for n in s.get("_negated", []):
        print("   negated", json.dumps(n, ensure_ascii=False)[:150])
    if s.get("_inferred"): print("   _inferred:", {k: v["value"] for k, v in s["_inferred"].items()})
    for k in ("_needsConfirmation", "_alternatives", "_uncertain"):
        if s.get(k): print("  ", k, json.dumps(s[k], ensure_ascii=False)[:200])
