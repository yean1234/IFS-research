"""G61 ① Unity 쪽 스펙 2.3 대조 — C# 표(ContourRender.cs)가 수치 원본(shared/lexicon/scene_params.v3.json render)과
스키마(scene-spec.v2.3.json enum)와 같은지, 파서가 2.3.0을 아는지, 셰이더 발광 항 이름이 C#과 같은지.
기존 관례(test_base_shapes.py가 BaseShapes.cs를 스키마·사전과 대조)를 따른다. Quest는 StreamingAssets 밖 파일을 읽을 수 없어
수치를 C#에 옮겨 적고, 어긋나면 이 테스트가 실패한다(docs/scene-spec-mapping.md 8.4·8.5절)."""
import json
import re

from ifs_chatbot.paths import REPO_ROOT, shared
from ifs_chatbot.scene_spec import SPEC_VERSION_V23, schema

RUNTIME = REPO_ROOT / "unity" / "Assets" / "IFS" / "Runtime"
CS = (RUNTIME / "SceneSpec" / "ContourRender.cs").read_text(encoding="utf-8")
PARAMS = json.loads(shared("lexicon", "scene_params.v3.json").read_text(encoding="utf-8"))
RENDER = PARAMS["render"]
SCHEMA = schema(SPEC_VERSION_V23)


def _strings(name: str) -> list[str]:
    body = re.search(rf"{name}\s*=\s*\{{([^}}]*)\}}", CS).group(1)
    return re.findall(r'"([^"]+)"', body)


def _numbers(name: str) -> list[float]:
    body = re.search(rf"{name}\s*=\s*\{{(.*?)\}};", CS, re.S).group(1)   # 들쭉날쭉 배열(new[] {{…}})까지
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", body)]


def _const(name: str) -> str:
    return re.search(rf"const \w+ {name} = (\"?)([^\";]+)\1;", CS).group(2)


def _enum(path: str) -> list[str]:
    obj, key = path.split(".")
    return [v for v in SCHEMA["properties"][obj]["properties"][key]["enum"] if v is not None]


def test_level_lists_match_the_schema_enums_in_order():
    assert _strings("RoundnessLevels") == _enum("form.roundness")
    assert _strings("AspectLevels") == _enum("form.aspect")
    assert _strings("EmissionLevels") == _enum("material.emission")


def test_superquadric_exponents_match_render_table():
    levels = _strings("RoundnessLevels")
    table = RENDER["contour"]["superquadric"]
    assert set(table) == set(levels)
    exps = _numbers("RoundnessExponent")
    for lvl, e in zip(levels, exps):
        assert table[lvl]["e1"] == table[lvl]["e2"] == e, lvl     # C#은 두 지수를 같게 둔다


def test_axis_ratios_match_render_table():
    levels = _strings("AspectLevels")
    ratios = _numbers("AspectRatio")
    assert len(ratios) == 3 * len(levels)
    table = RENDER["contour"]["aspectRatios"]
    assert set(table) == set(levels)
    for i, lvl in enumerate(levels):
        assert ratios[3 * i:3 * i + 3] == table[lvl], lvl
        assert max(table[lvl]) == 1.0, "긴 축 = 1(layout.size 뜻 유지)"
    assert _const("AspectAxisDefault") == RENDER["contour"]["aspectAxisDefault"]


def test_emission_intensities_match_render_table():
    levels = _strings("EmissionLevels")
    assert dict(zip(levels, _numbers("EmissionIntensityTable"))) == RENDER["emission"]["intensity"]
    assert RENDER["emission"]["bloom"] is False and RENDER["emission"]["color"] == "drawn_base_color"


def test_mesh_grid_and_params_version():
    mesh = RENDER["contour"]["mesh"]
    assert int(_const("LongitudeSegments")) == mesh["longitudeSegments"]
    assert int(_const("LatitudeSegments")) == mesh["latitudeSegments"]
    assert float(_const("UnitDiameter")) == mesh["unitDiameter"]
    assert _const("ParamsVersion") == f'{PARAMS["lexiconId"]}/{PARAMS["lexiconVersion"]}', \
        "scene_params.v3.json 수치를 바꾸면 lexiconVersion을 올리고 C# 표와 ParamsVersion을 같이 고친다"


def test_unity_parser_knows_23_and_shaders_have_the_emission_term():
    spec_cs = (RUNTIME / "SceneSpec" / "SceneSpecV2.cs").read_text(encoding="utf-8")
    assert f'SpecVersionV23 = "{SPEC_VERSION_V23}"' in spec_cs
    assert re.search(r"SupportedSpecVersions = \{[^}]*SpecVersionV23[^}]*\}", spec_cs)
    rend = (RUNTIME / "Rendering" / "FormRenderers.cs").read_text(encoding="utf-8")
    prop = re.search(r'EmissionProperty = "(\w+)"', rend).group(1)
    shaders = RUNTIME / "Resources" / "IFS"
    for f in ("SceneSpecOpaque.shader", "SceneSpecFade.shader", "SceneSpecMist.shader"):
        assert f'{prop} ("' in (shaders / f).read_text(encoding="utf-8"), f
    common = (shaders / "IFSSceneSpecCommon.cginc").read_text(encoding="utf-8")
    assert f"o.Emission += {prop}.rgb" in common
    assert "_EMISSION" not in common.replace("_EMISSION 키워드", ""), "Built-in Standard 발광 키워드를 쓰지 않는다"
