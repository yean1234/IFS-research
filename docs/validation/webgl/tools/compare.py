"""미리보기 캡처 두 벌을 spec별로 비교한다(D4). 기준(예: 에디터 PreviewCapture)과 대상(WebGL·Windows 플레이어).

입력 폴더마다 <spec>_scene.png, <spec>_black.png, <spec>_white.png(같은 해상도)가 있어야 한다.
  덮임 a = 1 − mean_c(lin(W) − lin(B)) (BatchCapture.Coverage와 같은 식), 덮인 화소 = a ≥ 0.02
  평균 색 ΔE00 = 덮인 화소(두 쪽 합집합)에서 장면 렌더의 평균 색(선형 평균 → sRGB → Lab) 사이 CIEDE2000
  화소 ΔE00 평균 = 덮인 화소(합집합)마다 ΔE00의 평균, 화면 전체 RGB 평균 절대 차(0–255), 최대 채널 차
  덮인 화소 차 = (대상 − 기준) / 기준

사용: python -I compare.py <기준 폴더> <대상 폴더> <결과 json> [--label-a editor --label-b player]
외부 패키지: numpy, Pillow. 네트워크를 쓰지 않는다.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

BACKGROUNDS = ("scene", "black", "white")


def srgb_to_linear(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_lab(lin):
    # sRGB(D65) 선형 → XYZ → Lab (ColorMetrics.cs와 같은 행렬·백색점)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ m.T
    white = np.array([0.95047, 1.0, 1.08883])
    t = xyz / white
    d = 6.0 / 29.0
    f = np.where(t > d ** 3, np.cbrt(t), t / (3 * d * d) + 4.0 / 29.0)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def ciede2000(lab1, lab2):
    """Sharma, Wu, Dalal (2005). 배열 브로드캐스트."""
    L1, a1, b1 = lab1[..., 0], lab1[..., 1], lab1[..., 2]
    L2, a2, b2 = lab2[..., 0], lab2[..., 1], lab2[..., 2]
    C1 = np.hypot(a1, b1)
    C2 = np.hypot(a2, b2)
    Cm = (C1 + C2) / 2
    G = 0.5 * (1 - np.sqrt(Cm ** 7 / (Cm ** 7 + 25.0 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dLp = L2 - L1
    dCp = C2p - C1p
    dh = h2p - h1p
    dh = np.where(C1p * C2p == 0, 0, np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh)))
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dh) / 2)
    Lpm = (L1 + L2) / 2
    Cpm = (C1p + C2p) / 2
    hsum = h1p + h2p
    hpm = np.where(C1p * C2p == 0, hsum,
                   np.where(np.abs(h1p - h2p) <= 180, hsum / 2,
                            np.where(hsum < 360, (hsum + 360) / 2, (hsum - 360) / 2)))
    T = (1 - 0.17 * np.cos(np.radians(hpm - 30)) + 0.24 * np.cos(np.radians(2 * hpm))
         + 0.32 * np.cos(np.radians(3 * hpm + 6)) - 0.20 * np.cos(np.radians(4 * hpm - 63)))
    dtheta = 30 * np.exp(-(((hpm - 275) / 25) ** 2))
    Rc = 2 * np.sqrt(Cpm ** 7 / (Cpm ** 7 + 25.0 ** 7))
    Sl = 1 + 0.015 * (Lpm - 50) ** 2 / np.sqrt(20 + (Lpm - 50) ** 2)
    Sc = 1 + 0.045 * Cpm
    Sh = 1 + 0.015 * Cpm * T
    Rt = -np.sin(np.radians(2 * dtheta)) * Rc
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def load(folder, spec, bg):
    p = os.path.join(folder, f"{spec}_{bg}.png")
    return np.asarray(Image.open(p).convert("RGB"), dtype=np.float64) / 255.0


def coverage(black, white):
    d = (srgb_to_linear(white) - srgb_to_linear(black)).mean(axis=-1)
    return np.clip(1 - d, 0, 1)


def compare_spec(a_dir, b_dir, spec):
    A = {bg: load(a_dir, spec, bg) for bg in BACKGROUNDS}
    B = {bg: load(b_dir, spec, bg) for bg in BACKGROUNDS}
    if A["scene"].shape != B["scene"].shape:
        raise ValueError(f"{spec}: 해상도가 다름 {A['scene'].shape} vs {B['scene'].shape}")
    cov_a = coverage(A["black"], A["white"])
    cov_b = coverage(B["black"], B["white"])
    mask_a, mask_b = cov_a >= 0.02, cov_b >= 0.02
    union = mask_a | mask_b
    lin_a, lin_b = srgb_to_linear(A["scene"]), srgb_to_linear(B["scene"])
    lab_a, lab_b = linear_to_lab(lin_a), linear_to_lab(lin_b)
    out = {
        "spec": spec,
        "coveredA": int(mask_a.sum()),
        "coveredB": int(mask_b.sum()),
        "coveredDiffRatio": float((mask_b.sum() - mask_a.sum()) / mask_a.sum()) if mask_a.sum() else None,
        "coverageMaskXor": int((mask_a ^ mask_b).sum()),
        "rgbMeanAbsDiff255": float(np.abs(A["scene"] - B["scene"]).mean() * 255),
        "rgbMaxAbsDiff255": int(round(np.abs(A["scene"] - B["scene"]).max() * 255)),
        "pixelDeltaE00MeanAll": float(ciede2000(lab_a, lab_b).mean()),
    }
    if union.any():
        de = ciede2000(lab_a[union], lab_b[union])
        mean_a = linear_to_lab(lin_a[union].mean(axis=0))
        mean_b = linear_to_lab(lin_b[union].mean(axis=0))
        out.update({
            "pixelDeltaE00MeanCovered": float(de.mean()),
            "pixelDeltaE00P95Covered": float(np.percentile(de, 95)),
            "meanColorDeltaE00": float(ciede2000(mean_a, mean_b)),
            "meanSrgb8A": [int(round(v)) for v in (A["scene"][union].mean(axis=0) * 255)],
            "meanSrgb8B": [int(round(v)) for v in (B["scene"][union].mean(axis=0) * 255)],
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a_dir")
    ap.add_argument("b_dir")
    ap.add_argument("out_json")
    ap.add_argument("--label-a", default="A")
    ap.add_argument("--label-b", default="B")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # 표를 파일로 돌려받을 때 한글이 깨지지 않게(Windows 기본 cp949)
    specs = sorted(f[: -len("_scene.png")] for f in os.listdir(args.a_dir) if f.endswith("_scene.png"))
    rows, missing = [], []
    for s in specs:
        if not all(os.path.exists(os.path.join(args.b_dir, f"{s}_{bg}.png")) for bg in BACKGROUNDS):
            missing.append(s)
            continue
        rows.append(compare_spec(args.a_dir, args.b_dir, s))

    def stat(key):
        v = [r[key] for r in rows if r.get(key) is not None]
        return {"mean": float(np.mean(v)), "max": float(np.max(v)), "n": len(v)} if v else None

    summary = {k: stat(k) for k in ("meanColorDeltaE00", "pixelDeltaE00MeanCovered", "pixelDeltaE00MeanAll",
                                     "rgbMeanAbsDiff255", "rgbMaxAbsDiff255")}
    cd = [abs(r["coveredDiffRatio"]) for r in rows if r.get("coveredDiffRatio") is not None]
    summary["absCoveredDiffRatio"] = {"mean": float(np.mean(cd)), "max": float(np.max(cd)), "n": len(cd)} if cd else None
    result = {"a": args.label_a, "b": args.label_b, "aDir": os.path.basename(os.path.normpath(args.a_dir)),
              "bDir": os.path.basename(os.path.normpath(args.b_dir)), "specs": rows, "missingInB": missing, "summary": summary}
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"| spec | 덮인 화소 {args.label_a} | {args.label_b} | 차(비율) | 평균 색 ΔE00 | 화소 ΔE00 평균(덮인 곳) | RGB 평균 차 | 최대 채널 차 |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in rows:
        print(f"| {r['spec']} | {r['coveredA']} | {r['coveredB']} | {r['coveredDiffRatio']:+.4f} | {r.get('meanColorDeltaE00', float('nan')):.3f} | "
              f"{r.get('pixelDeltaE00MeanCovered', float('nan')):.3f} | {r['rgbMeanAbsDiff255']:.3f} | {r['rgbMaxAbsDiff255']} |")
    print(json.dumps(summary, ensure_ascii=False))
    if missing:
        print("대상에 없는 spec:", ", ".join(missing), file=sys.stderr)


if __name__ == "__main__":
    main()
