"""비교 시트 — 문항 id별 v0 / v1 / 조건 2(라이브 v1) 캡처를 나란히. 칸마다 [장면 축소 | 형상 주변 확대(_detail)].

  py -3.11 docs/validation/mock-forms/make_sheets.py      (PIL 필요, 시스템 Python 3.11)

입력: capture/*.png, capture/report.json. 출력: sheets/sheet_01.png …(한 장 12행).
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
CAP = HERE / "capture"
OUT = HERE / "sheets"
FONT = "C:/Windows/Fonts/malgun.ttf"
FONT_B = "C:/Windows/Fonts/malgunbd.ttf"
ROWS = 12
T = 230            # 썸네일 한 변
LABEL_W = 250
PAD = 6
HEAD_H = 70
ROW_H = T + 34

LABELS = {
    "M01": "안개·잿빛·방을 채울 만큼", "M02": "검은 연기·조금 비침", "M03": "구름이에요·하양",
    "M04": "김·색 없음·거의 투명", "M05": "덩어리·남색·주먹만", "M06": "엉킨 실 뭉치·빨강+파랑",
    "M07": "뭉치·살구색·말랑", "M08": "껍질·갈색·가슴을 덮음", "M09": "얇은 막·연두·반투명",
    "M10": "달걀 껍데기·하양·금 감", "M11": "파란 조각·엄지손톱만", "M12": "유리 파편·거의 투명",
    "M13": "회색 부스러기·깨알만", "M14": "둥근 공·주황·매끈", "M15": "네모난 상자·검정",
    "M16": "납작한 돌·회색+흰 줄·9 cm", "M17": "뾰족한 가시·빨강", "M18": "엉킨 검은 실",
    "M19": "가는 선·금빛·40 cm", "M20": "종이 한 장·하양·A4", "M21": "얇은 천·보라+남색·반투명",
    "M22": "물방울·색 없음·1 cm", "M23": "웅덩이·탁한 초록·발밑", "M24": "꿀 같은 액체·노랑",
    "M25": "작은 빛·하양·구슬만", "M26": "촛불 불꽃·파랑+주황", "M27": "노란빛·눈부심·머리 위",
    "M28": "구멍·안은 깜깜", "M29": "텅 빈 공간·색 없음", "M30": "웅크린 작은 사람·잿빛",
    "M31": "까만 고양이·말려 있음", "M32": "작은 새·하늘색+노랑", "M33": "모름(멍함)",
    "M34": "답답함(느낌만)", "M35": "무거움·가라앉음(느낌)", "M36": "초조함·들썩(느낌)",
}


def fit(img: Image.Image, box: int) -> Image.Image:
    im = img.convert("RGB")
    im.thumbnail((box, box), Image.LANCZOS)
    bg = Image.new("RGB", (box, box), (40, 40, 40))
    bg.paste(im, ((box - im.width) // 2, (box - im.height) // 2))
    return bg


def cell(name: str, rep: dict) -> tuple[Image.Image, str]:
    w = 2 * T + PAD
    canvas = Image.new("RGB", (w, T), (40, 40, 40))
    scene, detail = CAP / f"{name}.png", CAP / f"{name}_detail.png"
    if scene.exists():
        canvas.paste(fit(Image.open(scene), T), (0, 0))
    if detail.exists():
        canvas.paste(fit(Image.open(detail), T), (T + PAD, 0))
    e = rep.get(f"{name}.json") or {}
    sil = e.get("silhouette") or {}
    cap = f"{e.get('renderPath', '없음')} · px {e.get('visiblePixels', '—')} · circ {sil.get('circularity', '—')} · comp {sil.get('components', '—')}"
    return canvas, cap


def main() -> None:
    rep = {e["spec"]: e for e in json.loads((CAP / "report.json").read_text(encoding="utf-8"))["specs"]}
    ids = sorted(LABELS)
    OUT.mkdir(exist_ok=True)
    f_lab = ImageFont.truetype(FONT_B, 22)
    f_sub = ImageFont.truetype(FONT, 17)
    f_cap = ImageFont.truetype(FONT, 14)
    f_head = ImageFont.truetype(FONT_B, 20)
    cols = [("v0 (조건 1)", "{id}.v0"), ("v1 (조건 1)", "{id}.v1"), ("조건 2 라이브 · v1", "{id}.live.v1")]
    col_w = 2 * T + PAD
    width = LABEL_W + len(cols) * (col_w + 2 * PAD) + PAD
    for si in range(0, len(ids), ROWS):
        chunk = ids[si:si + ROWS]
        height = HEAD_H + len(chunk) * (ROW_H + PAD) + 40
        sheet = Image.new("RGB", (width, height), (250, 250, 250))
        d = ImageDraw.Draw(sheet)
        d.text((PAD, 8), "목업(합성) 심상 → SceneSpec → Unity 캡처", font=f_head, fill=(20, 20, 20))
        d.text((PAD, 38), "칸마다 왼쪽 = 장면 전체(축소), 오른쪽 = 형상 주변 확대. 회색 칸 = 캡처 없음(조건 2는 6개만)", font=f_cap, fill=(80, 80, 80))
        for ci, (title, _) in enumerate(cols):
            x = LABEL_W + ci * (col_w + 2 * PAD) + PAD
            d.text((x, HEAD_H - 22), title, font=f_head, fill=(20, 20, 20))
        for ri, iid in enumerate(chunk):
            y = HEAD_H + ri * (ROW_H + PAD)
            d.text((PAD, y + 4), iid, font=f_lab, fill=(10, 10, 10))
            words = LABELS[iid].split("·")
            line, ly = "", y + 36
            for wd in words:                      # 라벨을 폭에 맞춰 줄바꿈
                cand = (line + "·" + wd) if line else wd
                if d.textlength(cand, font=f_sub) > LABEL_W - 2 * PAD and line:
                    d.text((PAD, ly), line, font=f_sub, fill=(40, 40, 40))
                    ly += 22
                    line = wd
                else:
                    line = cand
            d.text((PAD, ly), line, font=f_sub, fill=(40, 40, 40))
            for ci, (_, pat) in enumerate(cols):
                name = pat.format(id=iid)
                x = LABEL_W + ci * (col_w + 2 * PAD) + PAD
                if (CAP / f"{name}.png").exists():
                    img, cap = cell(name, rep)
                    sheet.paste(img, (x, y))
                    d.text((x, y + T + 6), cap, font=f_cap, fill=(60, 60, 60))
                else:
                    d.rectangle([x, y, x + col_w, y + T], fill=(225, 225, 225))
        d.text((PAD, height - 30), "AI 판정 자료. 합성 대사(참여자 데이터 아님). docs/validation/mock-forms/README.md", font=f_cap, fill=(90, 90, 90))
        out = OUT / f"sheet_{si // ROWS + 1:02d}.png"
        sheet.save(out, optimize=True)
        print(out.name, sheet.size)


if __name__ == "__main__":
    main()
