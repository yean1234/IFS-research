"""비교 시트: 문장 id별 한 줄에 규칙 경로 PNG와 생성 경로(Unity 캡처) PNG를 나란히 둔다.

  python tools/gen3d/compare_sheet.py --run <이름> [--rows-per-sheet 10] [--view oblique]

입력(모두 OUT_ROOT/<run>/ 아래, 저장소 밖):
  rule_capture/<id>_detail.png (또는 <id>.png)   기존 BatchCapture(SceneSpec) 결과
  <pipeline>-<mode>/capture/<id>_<view>.png       Gen3DCapture 결과
  sdxl-triposr-<mode>/images/<id>.png             text→image 중간 결과(참고 열)
출력: OUT_ROOT/compare/<run>_sheet_<n>.png. 시트에는 문장 원문을 넣지 않고 id만 쓴다(원문 대응표는 inputs/ 아래).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_ROOT, assert_outside_repo, read_json  # noqa: E402

CELL = 256
LABEL_W = 90
HEAD_H = 44


def columns(run_dir: Path, view: str):
    cols = [("rule (SceneSpec)", lambda i: _first(run_dir / "rule_capture", [f"{i}_detail.png", f"{i}.png"]))]
    for mode in ("rules", "llm"):
        cols += [
            (f"Shap-E [{mode}]", lambda i, m=mode: run_dir / f"shap-e-{m}" / "capture" / f"{i}_{view}.png"),
            (f"SDXL img [{mode}]", lambda i, m=mode: run_dir / f"sdxl-triposr-{m}" / "images" / f"{i}.png"),
            (f"TripoSR [{mode}]", lambda i, m=mode: run_dir / f"sdxl-triposr-{m}" / "capture" / f"{i}_{view}.png"),
        ]
    return cols


def _first(d: Path, names):
    for n in names:
        if (d / n).exists():
            return d / n
    return d / names[0]


def font(size):
    for f in ("arial.ttf", "C:/Windows/Fonts/arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def fit(p: Path) -> Image.Image:
    if not p.exists():
        im = Image.new("RGB", (CELL, CELL), (40, 40, 40))
        ImageDraw.Draw(im).text((10, CELL // 2 - 8), "missing", fill=(200, 80, 80), font=font(16))
        return im
    im = Image.open(p).convert("RGB")
    w, h = im.size
    s = min(w, h)                                  # 가운데 정사각형으로 자른 뒤 축소
    im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
    return im.resize((CELL, CELL), Image.LANCZOS)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--rows-per-sheet", type=int, default=10)
    ap.add_argument("--view", default="oblique")
    a = ap.parse_args(argv)
    run_dir = assert_outside_repo(OUT_ROOT / a.run)
    out_dir = assert_outside_repo(OUT_ROOT / "compare")
    out_dir.mkdir(parents=True, exist_ok=True)
    ids = [r["id"] for r in read_json(run_dir / "inputs" / "sentences.json")]
    cols = columns(run_dir, a.view)
    f_head, f_id = font(15), font(22)
    for n, start in enumerate(range(0, len(ids), a.rows_per_sheet), 1):
        chunk = ids[start:start + a.rows_per_sheet]
        W = LABEL_W + CELL * len(cols)
        H = HEAD_H + CELL * len(chunk)
        sheet = Image.new("RGB", (W, H), (255, 255, 255))
        d = ImageDraw.Draw(sheet)
        for c, (name, _) in enumerate(cols):
            d.text((LABEL_W + c * CELL + 8, 12), name, fill=(0, 0, 0), font=f_head)
        for r, sid in enumerate(chunk):
            y = HEAD_H + r * CELL
            d.text((10, y + CELL // 2 - 12), sid, fill=(0, 0, 0), font=f_id)
            for c, (_, path_of) in enumerate(cols):
                sheet.paste(fit(path_of(sid)), (LABEL_W + c * CELL, y))
        p = out_dir / f"{a.run}_sheet_{n}.png"
        sheet.save(p)
        print(p)


if __name__ == "__main__":
    main()
