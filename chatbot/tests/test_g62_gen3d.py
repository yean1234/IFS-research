"""G62: 생성 형태 메시 후보의 파이프라인 통합(form_assets.py·selection.py·server.py, selection 0.3).
플래그 꺼짐 = 기존 출력 불변, 켜짐 + 합성 사이드카(임시 폴더의 작은 가짜 GLB) = 후보에 포함, 차단·실패·관문 탈락 = 절차 메시만,
selection 0.3 스키마, 0.1·0.2 파일 읽기 호환. 모든 대사는 합성이다. 생성 모델·torch를 부르지 않는다."""
import hashlib
import json
import re
import struct
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from ifs_chatbot.candidates import candidates_bytes, generate
from ifs_chatbot.config import Gen3DConfig, load_config
from ifs_chatbot.controller import Runtime
from ifs_chatbot.form_assets import FormAssetStore, bare_sha, source_key
from ifs_chatbot.paths import REPO_ROOT, shared
from ifs_chatbot.server import create_app
from ifs_chatbot.simulate import drive

SCHEMA02 = json.loads(shared("schemas", "selection.v0.2.json").read_text(encoding="utf-8"))
SCHEMA03 = json.loads(shared("schemas", "selection.v0.3.json").read_text(encoding="utf-8"))
V02, V03 = Draft202012Validator(SCHEMA02), Draft202012Validator(SCHEMA03)

T_FEEL = "가슴 안쪽이 답답하고 무거운 느낌이에요."          # 빈 자리 여럿 → 절차 후보 4
T_ALL = "까만 덩어리가 눈앞 가까이 있어요. 크고 무겁고 매끈해요. 안 움직여요. 불투명해요. 어두워요."   # 절차 후보 1(건너뜀)


# ── 합성 GLB·사이드카 ────────────────────────────────────────────────────────
def ASSET_ID(name: str) -> str:
    return hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]


def tiny_glb(height: float = 0.6) -> bytes:
    """사면체 하나(가장 긴 변 1.0, 피벗 bottom-center: y 최저 0, x·z 가운데 0). height로 자산마다 바이트를 다르게. 연구 자료가 아니다."""
    pos = [(-0.5, 0.0, -0.25), (0.5, 0.0, -0.25), (0.0, 0.0, 0.25), (0.0, height, 0.0)]
    idx = [0, 1, 2, 0, 3, 1, 1, 3, 2, 2, 3, 0]
    pb = b"".join(struct.pack("<3f", *p) for p in pos)
    ib = b"".join(struct.pack("<H", i) for i in idx)
    ib += b"\x00" * ((4 - len(ib) % 4) % 4)
    binary = pb + ib
    gltf = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
            "buffers": [{"byteLength": len(binary)}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(pb)},
                            {"buffer": 0, "byteOffset": len(pb), "byteLength": len(idx) * 2}],
            "accessors": [{"bufferView": 0, "componentType": 5126, "count": 4, "type": "VEC3",
                           "min": [-0.5, 0.0, -0.25], "max": [0.5, height, 0.25]},
                          {"bufferView": 1, "componentType": 5123, "count": len(idx), "type": "SCALAR"}]}
    js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    js += b" " * ((4 - len(js) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(binary)
    return (struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js
            + struct.pack("<II", len(binary), 0x004E4942) + binary)


def write_asset(folder: Path, key: str, asset_id: str, seed: int = 0, status: str = "ok", passed: bool = True,
                glb: bytes | None = None, sha_override: str | None = None, block_reason: str | None = None,
                tokens: list | None = None) -> Path:
    """form-asset.v0 형식의 합성 사이드카(+ ok면 작은 가짜 GLB). asset_id는 사람이 읽는 테스트 이름이고, 사이드카 assetId는
    스키마대로 그 sha256 앞 16자다(ASSET_ID로 바꿔 비교). tokens = prompt.tokens(없으면 '덩어리' 하나, G62-i 판정에는 맞지 않음)."""
    folder.mkdir(parents=True, exist_ok=True)
    data = glb if glb is not None else tiny_glb(0.3 + 0.1 * seed + (int(hashlib.sha256(asset_id.encode()).hexdigest()[:4], 16) % 97) / 1000)
    aid = ASSET_ID(asset_id)
    name = f"{aid}.glb"
    if status == "ok":
        (folder / name).write_bytes(data)
    ok = status == "ok"
    side = {
        "schema": "form-asset.v0", "assetId": aid, "status": status,
        "blockReason": None if ok else ("person_like" if status == "blocked" else None),
        "glb": name if ok else None,
        "glbSha256": sha_override or (hashlib.sha256(data).hexdigest() if ok else None),
        "pipeline": "sdxl-triposg",
        "models": [{"name": "shape", "repo": "none/synthetic-test", "revision": "0" * 40, "weightsSha256": None}],
        "seed": seed,
        "prompt": {"text": "a single lump, matte gray clay, plain background", "lexiconVersion": "test",
                   "tokens": tokens if tokens is not None else
                   [{"en": "lump", "ko": "덩어리", "charSpan": [3, 6], "slot": "shape_noun"}]},
        "sourceTextSha256": key,
        "normalization": {"longestEdge": 1.0, "pivot": "bottom-center",
                          "bboxBefore": {"min": [-1.0, 0.0, -0.5], "max": [1.0, 1.2, 0.5]},
                          "bboxAfter": {"min": [-0.5, 0.0, -0.25], "max": [0.5, 0.6, 0.25]}, "scaleApplied": 0.5} if ok else None,
        "covariates": {"axisRatios": [1.0, 0.6, 0.5] if ok else None, "thinRisk": False, "familiarObjectStated": False},
        "gate": {"personLikeScore": 0.01 if ok else None, "passed": passed if ok else None},
    }
    if status == "failed":
        side["error"] = block_reason
    p = folder / f"{aid}.json"
    p.write_text(json.dumps(side, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def cfg(tmp_path, gen3d: bool | None, assets: Path | None = None, default: str | None = None, preview: str = "image"):
    """preview = image(기본, 서버 안 가짜 렌더러 — 생성 형태를 그릴 수 있음) | none(글 요약 — 생성 후보를 내지 않음)."""
    over = {"llm.backend": "offline", "guard.model_backend": "none", "session.log_dir": str(tmp_path / "logs"),
            "preview.mode": preview, "preview.image_player": "fake" if preview == "image" else ""}
    c = load_config("v4").with_overrides(**over)
    if gen3d is not None:
        c = c.with_overrides(**{"gen3d.enabled": gen3d, "gen3d.assets_dir": str(assets or tmp_path / "assets"),
                                "gen3d.default_form_source": default})
    return c


def done_session(rt, sid, text):
    s = rt.new_session("static", sid)
    drive(s, {"id": sid, "replies": ["뭔가 있어요", "가슴이요", "그대로예요", "없어요"], "defaultReply": "없어요",
              "confirm": {"edit": text}})
    assert s.state == "done"
    return s


def key_of(s) -> str:
    return source_key(s.scene_spec)


def strip_times(obj):
    """시각 필드(…At, at)와 로컬 경로(selectionPath)를 뺀 사본(실행마다 다른 값)."""
    if isinstance(obj, dict):
        return {k: strip_times(v) for k, v in obj.items()
                if not (k == "at" or k.endswith("At") or k in ("since", "selectionPath", "path"))}
    if isinstance(obj, list):
        return [strip_times(v) for v in obj]
    return obj


def valid(data, validator):
    errs = [f"{list(e.path)}: {e.message}" for e in validator.iter_errors(json.loads(json.dumps(data, ensure_ascii=False)))]
    assert not errs, errs[:3]


def run_flow(rt, sid, text, choose=None, form_edit=None, before_start=None):
    s = done_session(rt, sid, text)
    if before_start:
        before_start(s)
    f = s.selection()
    v = f.start()
    if f.stage == "selecting":
        cid = choose(v) if choose else v["candidates"][0]["id"]
        f.select(cid)
    if form_edit is not None:
        f.adjust("form", form_edit)
    f.finish()
    return s, f


# ── 설정 ────────────────────────────────────────────────────────────────────
def test_gen3d_off_by_default_and_on_only_in_gen3d_profile():
    assert Gen3DConfig().enabled is False
    assert load_config("v4").gen3d.enabled is False
    assert load_config("default").gen3d.enabled is False
    on = load_config("v4-gen3d")
    assert on.gen3d.enabled is True and on.gen3d.max_candidates == 2
    assert on.gen3d.default_form_source == "auto" and Gen3DConfig().default_form_source == "procedural"   # G62-i
    # v4-gen3d는 v4와 [gen3d]만 다르다 — G73(CP13b)부터 다시 적기 때문에 [selection] protocol(0.8.0)·table(3.0.0)도 다르다
    a, b = load_config("v4").to_dict(), on.to_dict()
    a.pop("source"), b.pop("source"), a.pop("gen3d"), b.pop("gen3d")
    assert (b["selection"].pop("protocol"), b["selection"].pop("table")) == ("selection_protocol.v0.8.json",
                                                                             "candidate_values.v3.json")
    a["selection"].pop("protocol"), a["selection"].pop("table")
    assert a == b


def test_chatbot_has_no_model_dependency():
    """챗봇은 생성 모델을 부르지 않는다(torch 등 의존 없음, 자산 폴더만 읽음)."""
    pyproject = (REPO_ROOT / "chatbot" / "pyproject.toml").read_text(encoding="utf-8")
    assert not re.search(r"torch|diffusers|transformers|trimesh", pyproject)
    src = (REPO_ROOT / "chatbot" / "ifs_chatbot" / "form_assets.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(import|from)\s+(torch|diffusers|transformers|httpx|requests)", src, re.M)


# ── 플래그 꺼짐 = 기존 출력 불변 ─────────────────────────────────────────────
def test_flag_off_output_identical_even_with_matching_assets(tmp_path):
    """같은 확정 텍스트를 (a) [gen3d] 없는 v4, (b) [gen3d] enabled = false + 맞는 사이드카가 있는 자산 폴더로 돌린다.
    후보 파일 바이트·selection.json(시각 빼고)·화면 응답·세션 로그 사건·Runtime.info가 같고, 0.2 그대로다."""
    assets = tmp_path / "assets"
    outs = []
    for name, flag in (("a", None), ("b", False)):
        rt = Runtime(cfg(tmp_path / name, flag, assets))
        holder = {}

        def seed_assets(s):
            write_asset(assets, key_of(s), "A-ok-0", seed=0)
            write_asset(assets, key_of(s), "A-ok-1", seed=1)

        s, f = run_flow(rt, "SYN-G62-OFF", T_FEEL, before_start=seed_assets)
        holder["cands"] = (f.dir / "candidates.json").read_bytes()
        holder["sel"] = strip_times(json.loads((f.dir / "selection.json").read_text(encoding="utf-8")))
        holder["view"] = strip_times(f.view())
        holder["events"] = strip_times([e for e in s.log.data["events"] if e["type"].startswith("selection:")])
        info = rt.info()
        info.pop("config")
        holder["info"] = info
        assert holder["cands"] == candidates_bytes(generate(s.scene_spec, s.id, rt.candidate_table))
        assert holder["sel"]["formatVersion"] == "ifs-selection/0.2"
        assert "form" not in holder["sel"] and "generation" not in holder["sel"]
        assert "gen3d" not in info and rt.form_assets is None
        valid(json.loads((f.dir / "selection.json").read_text(encoding="utf-8")), V02)
        assert not list(f.dir.glob("form-asset-*"))
        outs.append(holder)
    assert outs[0] == outs[1]


# ── 켜짐 + 합성 사이드카 ─────────────────────────────────────────────────────
def test_flag_on_adds_generated_candidates_and_records_choice(tmp_path):
    assets = tmp_path / "assets"
    rt = Runtime(cfg(tmp_path, True, assets))
    seen = {}

    def seed_assets(s):
        k = key_of(s)
        write_asset(assets / "run1", k, "A-ok-1", seed=1)
        write_asset(assets / "run1", k, "A-ok-0", seed=0)
        write_asset(assets / "run2", k, "A-ok-2", seed=2)                      # 상한(2) 초과
        write_asset(assets / "run2", "0" * 64, "A-other", seed=0)              # 다른 텍스트 — 무시
        seen["key"] = k

    def pick_generated(v):
        gens = [c for c in v["candidates"] if c["generated"]]
        assert [c["asset"]["assetId"] for c in sorted(gens, key=lambda c: c["index"])] == [ASSET_ID("A-ok-0"), ASSET_ID("A-ok-1")]
        assert all(c["asset"]["glbUrl"].endswith("/asset.glb") for c in gens)
        seen["view"] = v
        return gens[0]["id"]

    s, f = run_flow(rt, "SYN-G62-ON", T_FEEL, choose=pick_generated, before_start=seed_assets)
    cands = json.loads((f.dir / "candidates.json").read_text(encoding="utf-8"))
    proc = generate(s.scene_spec, s.id, rt.candidate_table)
    # 절차 후보는 그대로 남고 생성 후보 2개가 뒤에 붙는다
    assert [c["id"] for c in cands["candidates"][:len(proc["candidates"])]] == [c["id"] for c in proc["candidates"]]
    gens = [c for c in cands["candidates"] if c.get("origin") == "generated"]
    assert len(gens) == 2 and all(c["id"].startswith("g-") and c["sources"]["form.type"] == "generated" for c in gens)
    assert all(c["overrides"] == proc["candidates"][0]["overrides"] for c in gens)   # 색·크기 등은 0번 후보와 같음
    assert sorted(cands["displayOrder"]) == sorted(c["id"] for c in cands["candidates"])
    assert cands["generation"]["lookupKey"] == seen["key"]
    assert [(r["assetId"], r["reason"]) for r in cands["generation"]["rejected"]] == [(ASSET_ID("A-ok-2"), "over_limit")]
    data = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    assert data["formatVersion"] == "ifs-selection/0.3"
    a = data["form"]["asset"]
    assert a["assetId"] == ASSET_ID("A-ok-0") and a["seed"] == 0 and a["pipeline"] == "sdxl-triposg"
    assert a["promptText"].startswith("a single") and a["models"][0]["name"] == "shape"
    copied = f.dir / a["glb"]
    assert copied.is_file() and hashlib.sha256(copied.read_bytes()).hexdigest() == a["glbSha256"]
    assert (f.dir / a["sidecar"]).is_file()
    assert data["sources"]["form.type"] == "generated_chosen"
    assert data["sourceDetails"]["form.type"]["generatedAsset"]["assetId"] == ASSET_ID("A-ok-0")
    assert data["sourceCounts"]["generated_chosen"] == 1
    assert data["generation"]["outcome"] == "generated_chosen" and data["generation"]["declined"] == [ASSET_ID("A-ok-1")]
    assert data["generation"]["shownOrder"] == [cid for cid in cands["displayOrder"] if cid.startswith("g-")]
    assert data["finalOverrides"] == {}                 # 생성 메시는 슬롯 값이 아니다(spec·덮어쓰기 불변)
    assert data["runnerReady"] is True
    valid(data, V03)
    valid(cands, Draft202012Validator(SCHEMA03["properties"]["candidates"] | {"$defs": SCHEMA03["$defs"]}))
    # 로컬 절대 경로를 기록에 쓰지 않는다
    assert str(assets) not in json.dumps(data, ensure_ascii=False) and str(assets) not in json.dumps(cands, ensure_ascii=False)
    # 세션 로그 사건에 생성 조회 요약
    ev = next(e for e in s.log.data["events"] if e["type"] == "selection:candidates")
    assert ev["payload"]["generation"]["offered"] == [ASSET_ID("A-ok-0"), ASSET_ID("A-ok-1")]


def test_flag_on_generated_candidate_forces_choice_even_when_procedural_skips(tmp_path):
    assets = tmp_path / "assets"
    rt = Runtime(cfg(tmp_path, True, assets))
    s = done_session(rt, "SYN-G62-SKIP", T_ALL)
    assert generate(s.scene_spec, s.id, rt.candidate_table)["selectionStep"] == "skip"
    write_asset(assets, key_of(s), "A-ok-0")
    f = s.selection()
    v = f.start()
    assert f.stage == "selecting" and len(v["candidates"]) == 2
    assert f.cands["generation"]["proceduralSelectionStep"] == "skip"
    f.select("none")                                   # 맞는 것이 없다 → 기준 후보(절차 0번)
    f.finish()
    data = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    assert data["form"]["asset"] is None and data["generation"]["outcome"] == "none"
    assert data["generation"]["declined"] == [ASSET_ID("A-ok-0")] and data["sources"]["form.type"] != "generated_chosen"
    valid(data, V03)


def test_form_edit_after_generated_choice_drops_asset(tmp_path):
    assets = tmp_path / "assets"
    rt = Runtime(cfg(tmp_path, True, assets))
    s, f = run_flow(rt, "SYN-G62-EDIT", T_FEEL, before_start=lambda s: write_asset(assets, key_of(s), "A-ok-0"),
                    choose=lambda v: next(c["id"] for c in v["candidates"] if c["generated"]), form_edit="shell")
    data = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    assert data["form"]["asset"] is None
    assert data["generation"]["assetDropped"]["reason"] == "form_edited"
    assert data["sources"]["form.type"] == "edited" and data["sourceCounts"]["generated_chosen"] == 0
    valid(data, V03)


@pytest.mark.parametrize("kind,reason", [("blocked", "blocked"), ("failed", "failed"), ("gate", "gate_not_passed"),
                                         ("sha", "glb_sha256_mismatch"), ("missing", "glb_missing")])
def test_blocked_or_failed_sidecars_leave_procedural_only(tmp_path, kind, reason):
    assets = tmp_path / "assets"
    rt = Runtime(cfg(tmp_path, True, assets))

    def seed(s):
        k = key_of(s)
        if kind == "blocked":
            write_asset(assets, k, "A-bad", status="blocked", block_reason="person_like")
        elif kind == "failed":
            write_asset(assets, k, "A-bad", status="failed", block_reason="oom")
        elif kind == "gate":
            write_asset(assets, k, "A-bad", passed=False)
        elif kind == "sha":
            write_asset(assets, k, "A-bad", sha_override="f" * 64)
        else:
            write_asset(assets, k, "A-bad")
            (assets / (ASSET_ID("A-bad") + ".glb")).unlink()

    s = done_session(rt, "SYN-G62-" + kind.upper(), T_FEEL)
    seed(s)
    f = s.selection()
    f.start()
    proc = generate(s.scene_spec, s.id, rt.candidate_table)
    assert [c["id"] for c in f.cands["candidates"]] == [c["id"] for c in proc["candidates"]]
    assert f.cands["displayOrder"] == proc["displayOrder"] and f.cands["selectionStep"] == proc["selectionStep"]
    assert [(r["assetId"], r["reason"]) for r in f.cands["generation"]["rejected"]] == [(ASSET_ID("A-bad"), reason)]
    f.select(f.cands["displayOrder"][0])
    f.finish()
    data = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    assert data["form"]["asset"] is None and data["generation"]["offered"] == []
    assert data["generation"]["outcome"] == "procedural_chosen"
    valid(data, V03)


def test_no_assets_folder_still_writes_03_with_empty_generation(tmp_path):
    rt = Runtime(cfg(tmp_path, True, tmp_path / "does-not-exist"))
    assert any("[gen3d]" in w for w in rt.warnings)
    s, f = run_flow(rt, "SYN-G62-NODIR", T_FEEL)
    data = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    assert data["formatVersion"] == "ifs-selection/0.3" and data["generation"]["offered"] == []
    assert rt.info()["gen3d"]["assetsDirExists"] is False
    valid(data, V03)


def test_store_lookup_is_deterministic_and_key_prefix_insensitive(tmp_path):
    k = "ab" * 32
    write_asset(tmp_path / "z", k, "B", seed=1)
    write_asset(tmp_path / "a", k, "A", seed=1)
    write_asset(tmp_path / "a", k, "C", seed=0)
    st = FormAssetStore(tmp_path, 2)
    r1, r2 = st.lookup("sha256:" + k.upper()), st.lookup(k)
    want = [x[1] for x in sorted([(0, ASSET_ID("C")), (1, ASSET_ID("A")), (1, ASSET_ID("B"))])][:2]
    assert [a["assetId"] for a in r1["offered"]] == [a["assetId"] for a in r2["offered"]] == want
    assert bare_sha("sha256:ABC") == "abc"


def test_glb_endpoint_serves_generated_asset_only_when_enabled(tmp_path):
    assets = tmp_path / "assets"
    rt = Runtime(cfg(tmp_path, True, assets))
    client = TestClient(create_app(runtime=rt, warmup=False))
    s = done_session(rt, "SYN-G62-API", T_FEEL)
    write_asset(assets, key_of(s), "A-ok-0")
    v = client.post(f"/api/sessions/{s.id}/candidates").json()
    gen = next(c for c in v["candidates"] if c["generated"])
    r = client.get(gen["asset"]["glbUrl"])
    assert r.status_code == 200 and r.content == (assets / (gen["asset"]["assetId"] + ".glb")).read_bytes() and r.headers["content-type"] == "model/gltf-binary"
    proc = next(c for c in v["candidates"] if not c["generated"])
    assert client.get(f"/api/sessions/{s.id}/candidates/{proc['id']}/asset.glb").status_code == 422

    rt_off = Runtime(cfg(tmp_path / "off", False, assets))
    c_off = TestClient(create_app(runtime=rt_off, warmup=False))
    s2 = done_session(rt_off, "SYN-G62-API2", T_FEEL)
    v2 = c_off.post(f"/api/sessions/{s2.id}/candidates").json()
    assert all("generated" not in c for c in v2["candidates"])
    assert c_off.get(f"/api/sessions/{s2.id}/candidates/{v2['candidates'][0]['id']}/asset.glb").status_code == 409


# ── 스키마 0.3 · 읽기 호환 ──────────────────────────────────────────────────
def test_selection_03_schema_extends_02_only():
    assert SCHEMA03["properties"]["formatVersion"]["const"] == "ifs-selection/0.3"
    assert SCHEMA03["$defs"]["source"]["enum"] == SCHEMA02["$defs"]["source"]["enum"] + ["generated_chosen"]
    assert set(SCHEMA03["properties"]) == set(SCHEMA02["properties"]) | {"form", "generation", "defaultFormSource"}
    Draft202012Validator.check_schema(SCHEMA03)


def test_02_files_still_validate_and_runner_reads_all_three_versions():
    """러너는 0.1·0.2·0.3을 모두 안다(C# 원문 대조). 플래그 꺼짐의 0.2 출력이 0.2 스키마로 유효한지는
    test_flag_off_output_identical_even_with_matching_assets, 0.2 파일의 러너 읽기는 FormAssetTests(C#)가 본다."""
    src = (REPO_ROOT / "unity/Assets/IFS/Runtime/Placement/PlacementSelection.cs").read_text(encoding="utf-8")
    known = re.search(r"KnownFormatVersions\s*=\s*\{([^}]*)\}", src).group(1)
    assert set(re.findall(r'"([^"]+)"', known)) == {"ifs-selection/0.1", "ifs-selection/0.2", "ifs-selection/0.3",
                                                    "ifs-selection/0.4"}       # 0.4 = G73 다시 적기(test_g73_resay_flow.py)
    s03 = re.search(r"SourceValues03\s*=\s*\{([^}]*)\}", src).group(1)
    assert re.findall(r'"([^"]+)"', s03) == SCHEMA03["$defs"]["source"]["enum"]


def test_form_asset_sidecar_schema_accepts_synthetic_sidecar_if_present(tmp_path):
    """다른 작업이 만드는 shared/schemas/form-asset.v0.json이 있으면 테스트의 합성 사이드카가 그 스키마를 통과해야 한다
    (챗봇이 읽는 필드와 생성 도구가 쓰는 필드가 어긋나지 않게). 아직 없으면 건너뜀."""
    p = shared("schemas", "form-asset.v0.json")
    if not p.is_file():
        pytest.skip("form-asset.v0.json 아직 없음")
    schema = json.loads(p.read_text(encoding="utf-8"))
    side = json.loads(write_asset(tmp_path, "cd" * 32, "A-schema").read_text(encoding="utf-8"))
    errs = [f"{list(e.path)}: {e.message}" for e in Draft202012Validator(schema).iter_errors(side)]
    assert not errs, errs[:5]


# ── 기본 형태 후보 설정([gen3d] default_form_source) ─────────────────────────
def _first_generated(v):
    return next(c["id"] for c in v["candidates"] if c["generated"])


def test_default_procedural_when_key_absent_keeps_rotation_and_no_preselection(tmp_path):
    assets = tmp_path / "assets"
    rt = Runtime(cfg(tmp_path, True, assets))            # default_form_source 키 없음 → procedural
    assert rt.form_assets.default_form_source == "procedural"
    seen = {}

    def choose(v):
        seen["v"] = v
        return _first_generated(v)

    s, f = run_flow(rt, "SYN-G62-DEFP", T_FEEL, before_start=lambda s: write_asset(assets, key_of(s), "A-ok-0"),
                    choose=choose)
    v = seen["v"]
    assert v["defaultCandidateId"] is None and v["defaultFormSource"] == "procedural"
    assert not any(c["default"] for c in v["candidates"])
    from ifs_chatbot.candidates import _display_offset
    n = len(f.cands["candidates"])
    off = _display_offset(s.id, n)
    assert f.cands["displayOrder"] == [f.cands["candidates"][(k + off) % n]["id"] for k in range(n)]
    data = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    assert data["defaultFormSource"] == "procedural" and data["generation"]["defaultFormSourceSetting"] == "procedural"
    assert data["selection"]["acceptedDefault"] is None and data["generation"]["acceptedDefault"] is None
    assert data["sources"]["form.type"] == "generated_chosen"
    assert data["sourceDetails"]["form.type"]["acceptedDefault"] is False
    valid(data, V03)


def test_default_generated_first_and_preselected_accepting_default(tmp_path):
    assets = tmp_path / "assets"
    rt = Runtime(cfg(tmp_path, True, assets, default="generated"))
    seen = {}

    def seed(s):
        write_asset(assets, key_of(s), "A-ok-1", seed=1)
        write_asset(assets, key_of(s), "A-ok-0", seed=0)

    def choose(v):
        seen["v"] = v
        return v["defaultCandidateId"]                   # 기본을 그대로 확정

    s, f = run_flow(rt, "SYN-G62-DEFG", T_FEEL, before_start=seed, choose=choose)
    v = seen["v"]
    first = v["candidates"][0]
    assert first["default"] and first["generated"] and first["asset"]["assetId"] == ASSET_ID("A-ok-0")
    assert v["defaultCandidateId"] == first["id"] and sum(c["default"] for c in v["candidates"]) == 1
    assert sum(1 for c in v["candidates"] if not c["generated"]) == 4      # 절차 후보는 대안으로 모두 남음
    data = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    assert data["defaultFormSource"] == "generated" and data["generation"]["defaultCandidateId"] == first["id"]
    assert data["selection"]["acceptedDefault"] is True and data["selection"]["displayPosition"] == 0
    assert data["sources"]["form.type"] == "generated_chosen"
    assert data["sourceDetails"]["form.type"]["acceptedDefault"] is True
    assert data["form"]["asset"]["assetId"] == ASSET_ID("A-ok-0")
    valid(data, V03)


@pytest.mark.parametrize("pick", ["procedural", "other_generated", "none"])
def test_default_generated_but_participant_changes(tmp_path, pick):
    assets = tmp_path / "assets"
    rt = Runtime(cfg(tmp_path, True, assets, default="generated"))

    def seed(s):
        write_asset(assets, key_of(s), "A-ok-0", seed=0)
        write_asset(assets, key_of(s), "A-ok-1", seed=1)

    def choose(v):
        if pick == "procedural":
            return next(c["id"] for c in v["candidates"] if not c["generated"])
        if pick == "other_generated":
            return next(c["id"] for c in v["candidates"] if c["generated"] and not c["default"])
        return "none"

    s, f = run_flow(rt, "SYN-G62-CHG-" + pick, T_FEEL, before_start=seed, choose=choose)
    data = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    assert data["defaultFormSource"] == "generated" and data["selection"]["acceptedDefault"] is False
    if pick == "other_generated":
        assert data["sources"]["form.type"] == "generated_chosen" and data["form"]["asset"]["assetId"] == ASSET_ID("A-ok-1")
        assert data["sourceDetails"]["form.type"]["acceptedDefault"] is False
    else:
        assert data["form"]["asset"] is None and data["sources"]["form.type"] != "generated_chosen"
    valid(data, V03)


@pytest.mark.parametrize("status", ["blocked", "failed", "absent"])
def test_default_generated_falls_back_to_procedural_with_reason(tmp_path, status):
    assets = tmp_path / "assets"
    rt = Runtime(cfg(tmp_path, True, assets, default="generated"))

    def seed(s):
        if status != "absent":
            write_asset(assets, key_of(s), "A-x", status=status, block_reason="synthetic")

    seen = {}

    def choose(v):
        seen["v"] = v
        return v["candidates"][0]["id"]

    s, f = run_flow(rt, "SYN-G62-FB-" + status, T_FEEL, before_start=seed, choose=choose)
    proc = generate(s.scene_spec, s.id, rt.candidate_table)
    assert f.cands["displayOrder"] == proc["displayOrder"]
    assert seen["v"]["defaultCandidateId"] is None
    data = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    assert data["defaultFormSource"] == "procedural"
    assert data["generation"]["defaultFormSourceSetting"] == "generated"
    assert data["generation"]["defaultFallbackReason"] == "no_generated_candidate"
    assert [r["reason"] for r in data["generation"]["rejected"]] == ([] if status == "absent" else [status])
    valid(data, V03)


def test_default_form_source_value_is_checked(tmp_path):
    with pytest.raises(ValueError):
        Runtime(cfg(tmp_path, True, tmp_path / "assets", default="llm"))


def test_flag_off_identical_with_either_default_setting(tmp_path):
    """플래그가 꺼져 있으면 default_form_source 값이 무엇이든 출력이 같다."""
    assets = tmp_path / "assets"
    outs = []
    for name, d in (("p", "procedural"), ("g", "generated")):
        rt = Runtime(cfg(tmp_path / name, False, assets, default=d))
        s, f = run_flow(rt, "SYN-G62-OFFD", T_FEEL, before_start=lambda s: write_asset(assets, key_of(s), "A-ok-0"))
        outs.append(((f.dir / "candidates.json").read_bytes(),
                     strip_times(json.loads((f.dir / "selection.json").read_text(encoding="utf-8")))))
    assert outs[0] == outs[1] and outs[0][1]["formatVersion"] == "ifs-selection/0.2"


# ── 미리보기: 생성 후보는 실제 GLB 형태로만 보인다 ───────────────────────────
def _png_comment(png: bytes) -> bool:
    return b"tEXtComment\x00form asset" in png


def test_none_preview_mode_offers_no_generated_candidates(tmp_path):
    """글 요약(none)으로는 생성 형태를 보일 수 없다 → 생성 후보를 내지 않고 사유(no_shape_preview)를 기록한다."""
    assets = tmp_path / "assets"
    rt = Runtime(cfg(tmp_path, True, assets, default="generated", preview="none"))
    s, f = run_flow(rt, "SYN-G62-NONE", T_FEEL, before_start=lambda s: write_asset(assets, key_of(s), "A-ok-0"))
    proc = generate(s.scene_spec, s.id, rt.candidate_table)
    assert [c["id"] for c in f.cands["candidates"]] == [c["id"] for c in proc["candidates"]]
    data = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    assert [(r["assetId"], r["reason"]) for r in data["generation"]["rejected"]] == [(ASSET_ID("A-ok-0"), "no_shape_preview")]
    assert data["defaultFormSource"] == "procedural" and data["generation"]["defaultFallbackReason"] == "no_generated_candidate"
    valid(data, V03)


def test_image_preview_draws_generated_candidate_from_glb(tmp_path):
    """image 경로: 생성 후보 PNG는 GLB로 그린 것(절차 0번 후보 그림과 다름), 고른 뒤 조절 화면(current)도 GLB.
    형태 조절을 바꾸면 current는 그 형태(절차 메시)로 돌아간다."""
    assets = tmp_path / "assets"
    rt = Runtime(cfg(tmp_path, True, assets, default="generated"))
    client = TestClient(create_app(runtime=rt, warmup=False))
    s = done_session(rt, "SYN-G62-IMG", T_FEEL)
    write_asset(assets, key_of(s), "A-ok-0")
    v = client.post(f"/api/sessions/{s.id}/candidates").json()
    gen = v["candidates"][0]
    assert gen["generated"] and gen["default"]
    proc0 = next(c for c in v["candidates"] if not c["generated"] and c["overrides"] == {})
    png_gen = client.get(f"/api/sessions/{s.id}/preview/{gen['id']}.png").content
    png_proc = client.get(f"/api/sessions/{s.id}/preview/{proc0['id']}.png").content
    assert _png_comment(png_gen) and not _png_comment(png_proc) and png_gen != png_proc
    v = client.post(f"/api/sessions/{s.id}/selection", json={"candidateId": gen["id"]}).json()
    assert v["currentAsset"]["assetId"] == ASSET_ID("A-ok-0")
    assert _png_comment(client.get(f"/api/sessions/{s.id}/preview/current.png").content)
    v = client.post(f"/api/sessions/{s.id}/adjust", json={"item": "form", "value": "shell"}).json()
    assert v["currentAsset"] is None
    assert not _png_comment(client.get(f"/api/sessions/{s.id}/preview/current.png").content)


def test_unreadable_glb_is_rejected_at_lookup(tmp_path):
    """sha256은 맞지만 미리보기·러너가 읽을 수 없는 GLB → 후보로 내지 않음(glb_unreadable)."""
    assets = tmp_path / "assets"
    rt = Runtime(cfg(tmp_path, True, assets, default="generated"))
    s = done_session(rt, "SYN-G62-JUNK", T_FEEL)
    write_asset(assets, key_of(s), "A-bad", glb=b"glTF\x02\x00\x00\x00" + b"\x00" * 40)
    f = s.selection()
    f.start()
    assert [(r["assetId"], r["reason"]) for r in f.cands["generation"]["rejected"]] == [(ASSET_ID("A-bad"), "glb_unreadable")]
    assert not any("asset" in c for c in f.cands["candidates"])


def test_image_asset_failure_drops_candidate_and_moves_default(tmp_path, monkeypatch):
    """플레이어가 생성 GLB 하나를 그리지 못하면(PreviewAssetError) 그 후보를 빼고(410) 사유를 기록한다. image 경로는 닫지 않는다.
    기본 후보였으면 남은 생성 후보가 기본이 된다."""
    from ifs_chatbot.preview import PreviewAssetError
    assets = tmp_path / "assets"
    rt = Runtime(cfg(tmp_path, True, assets, default="generated"))
    client = TestClient(create_app(runtime=rt, warmup=False))
    s = done_session(rt, "SYN-G62-FAIL", T_FEEL)
    write_asset(assets, key_of(s), "A-ok-0", seed=0)
    write_asset(assets, key_of(s), "A-ok-1", seed=1)
    v = client.post(f"/api/sessions/{s.id}/candidates").json()
    first = v["candidates"][0]
    real = rt.preview.renderer.render

    def flaky(spec_json, overrides, asset=None):
        if asset is not None and asset["assetId"] == ASSET_ID("A-ok-0"):
            raise PreviewAssetError("synthetic draw failure")
        return real(spec_json, overrides, asset)

    monkeypatch.setattr(rt.preview.renderer, "render", flaky)
    r = client.get(f"/api/sessions/{s.id}/preview/{first['id']}.png")
    assert r.status_code == 410 and rt.preview.image_ok
    v = client.get(f"/api/sessions/{s.id}/selection").json()
    assert first["id"] not in [c["id"] for c in v["candidates"]]
    assert v["defaultCandidateId"] == v["candidates"][0]["id"] and v["candidates"][0]["asset"]["assetId"] == ASSET_ID("A-ok-1")
    f = s.selection()
    data = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    assert [(d["assetId"], d["reason"], d["source"]) for d in data["generation"]["previewDropped"]] == \
        [(ASSET_ID("A-ok-0"), "preview_failed", "server:image")]
    assert [o["assetId"] for o in data["generation"]["offered"]] == [ASSET_ID("A-ok-1")]
    valid(data, V03)


def test_webgl_asset_failure_report_drops_last_generated_and_skips(tmp_path):
    """브라우저(WebGL)가 asset_failed를 알리면 그 후보를 뺀다. 생성 후보가 모두 빠졌고 절차 후보만이면 건너뛸 세션(G34)은 건너뜀으로."""
    assets = tmp_path / "assets"
    rt = Runtime(cfg(tmp_path, True, assets, default="generated"))
    s = done_session(rt, "SYN-G62-WGL", T_ALL)
    write_asset(assets, key_of(s), "A-ok-0")
    f = s.selection()
    v = f.start()
    gid = v["defaultCandidateId"]
    assert f.stage == "selecting" and gid
    with pytest.raises(Exception):
        f.client_preview("asset_failed", "webgl", "selecting", "no candidate", None)
    v = f.client_preview("asset_failed", "webgl", "selecting", "SetFormAssetJson error", {"candidateId": gid})
    assert f.stage == "adjusting" and v["skipped"] is True
    data = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    assert data["generation"]["outcome"] == "skipped" and data["defaultFormSource"] == "procedural"
    assert data["generation"]["defaultFallbackReason"] == "preview_failed"
    assert data["generation"]["previewDropped"][0]["source"] == "client:webgl"
    f.finish()
    valid(json.loads((f.dir / "selection.json").read_text(encoding="utf-8")), V03)


def test_downgrade_to_text_summary_drops_generated(tmp_path):
    """선택 중 미리보기가 글 요약으로 내려가면 남은 생성 후보를 뺀다(형태를 보일 수 없음)."""
    assets = tmp_path / "assets"
    rt = Runtime(cfg(tmp_path, True, assets))
    s = done_session(rt, "SYN-G62-DOWN", T_FEEL)
    write_asset(assets, key_of(s), "A-ok-0")
    f = s.selection()
    f.start()
    assert any("asset" in c for c in f.cands["candidates"])
    f.client_preview("fallback", "image", "selecting", "synthetic", None)
    assert f.preview_mode == "none" and not any("asset" in c for c in f.cands["candidates"])
    data = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    assert data["generation"]["previewDropped"][0]["reason"] == "no_shape_preview"


def test_queue_player_without_form_asset_support_never_shows_procedural_look(tmp_path):
    """G62 전에 빌드한 플레이어(요청의 formAsset을 모르고 절차 메시로 그림)를 흉내 낸 가짜 플레이어: 생성 후보 그림을 쓰지 않고
    그 후보를 뺀다(410, preview_failed). image 경로 자체는 닫지 않는다."""
    player = Path(__file__).parent / "fixtures" / "fake_preview_player.py"
    assets = tmp_path / "assets"
    c = cfg(tmp_path, True, assets, default="generated").with_overrides(
        **{"preview.image_player": str(player), "preview.queue_dir": str(tmp_path / "q")})
    rt = Runtime(c)
    client = TestClient(create_app(runtime=rt, warmup=False))
    try:
        s = done_session(rt, "SYN-G62-OLD", T_FEEL)
        write_asset(assets, key_of(s), "A-ok-0")
        v = client.post(f"/api/sessions/{s.id}/candidates").json()
        gid = v["defaultCandidateId"]
        r = client.get(f"/api/sessions/{s.id}/preview/{gid}.png")
        assert r.status_code == 410 and rt.preview.image_ok
        v = client.get(f"/api/sessions/{s.id}/selection").json()
        assert not any(c.get("generated") for c in v["candidates"]) and v["defaultFormSource"] == "procedural"
    finally:
        rt.preview.close()


def test_web_and_unity_bridge_wire_glb_preview():
    """브라우저 쪽(stage.js)이 생성 후보에 GLB를 얹어 찍고(setFormAsset), 실패를 asset_failed로 알리며, WebGL 페이지 API와 Unity 다리가
    같은 이름을 쓴다(원문 대조 — Unity WebGL 빌드는 이 테스트에서 돌리지 않는다)."""
    js = (REPO_ROOT / "chatbot/ifs_chatbot/web/stage.js").read_text(encoding="utf-8")
    assert "setFormAsset(" in js and '"asset_failed"' in js and "Preview.node(c.id, c.summary, c.overrides, c.asset)" in js
    page = (REPO_ROOT / "unity/Assets/WebGLTemplates/IFSPreview/index.html").read_text(encoding="utf-8")
    assert "setFormAsset: function" in page and "'SetFormAssetJson'" in page
    bridge = (REPO_ROOT / "unity/Assets/IFS/Runtime/Preview/PreviewBridge.cs").read_text(encoding="utf-8")
    assert "public void SetFormAssetJson(string json)" in bridge
