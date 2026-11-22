"""gen3d 실험 경로의 공통 도구 — 경로, 해시, 모델 출처 기록, VRAM 측정.

실험용 별도 경로다(docs/gen3d-feasibility.md). 기존 SceneSpec 파이프라인과 섞지 않는다.
- 산출물(GLB·PNG·메타데이터)은 저장소 밖 OUT_ROOT에 쓴다(AGENTS.md 원칙 6).
- 모델 가중치는 HuggingFace 캐시(저장소 밖)에서 읽는다. 출처는 저장소 ID + 리비전(커밋 해시) + 파일 sha256으로 남긴다(원칙 5).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHATBOT = REPO / "chatbot"
# 저장소 밖 기본 출력 폴더. 환경 변수 GEN3D_OUT으로 바꿀 수 있다.
OUT_ROOT = Path(os.environ.get("GEN3D_OUT", str(REPO.parent / "gen3d-out")))
# 저장소 밖에 클론한 외부 코드(TripoSR 등). 환경 변수 GEN3D_MODELS로 바꿀 수 있다.
MODELS_ROOT = Path(os.environ.get("GEN3D_MODELS", str(REPO.parent / "gen3d-models")))


def assert_outside_repo(p: Path) -> Path:
    """참여자 문장으로 만든 산출물이 저장소 안에 쓰이지 않게 막는다(원칙 6)."""
    p = Path(p).resolve()
    try:
        p.relative_to(REPO)
    except ValueError:
        return p
    raise SystemExit(f"출력 폴더가 저장소 안입니다: {p}. 저장소 밖 폴더를 쓰세요(AGENTS.md 원칙 6).")


def sha256_file(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def hf_provenance(repo_id: str, patterns: tuple[str, ...] = (".safetensors", ".ckpt", ".bin", ".pt", ".onnx")) -> dict:
    """HF 캐시에 받은 스냅숏의 리비전(커밋 해시)과 가중치 파일 sha256.

    캐시 폴더 구조: models--{org}--{name}/snapshots/{commit}/... 내려받기를 하지 않고 이미 있는 것만 읽는다.
    """
    from huggingface_hub import snapshot_download

    path = Path(snapshot_download(repo_id, local_files_only=True))
    files = {}
    for f in sorted(path.rglob("*")):
        if f.is_file() and f.suffix in patterns:
            files[f.relative_to(path).as_posix()] = {"sha256": sha256_file(f), "bytes": f.stat().st_size}
    return {"repo": repo_id, "revision": path.name, "files": files}


def git_head(path: Path) -> str | None:
    head = path / ".git" / "HEAD"
    if not head.exists():
        return None
    ref = head.read_text().strip()
    if ref.startswith("ref:"):
        rp = path / ".git" / ref.split(" ", 1)[1]
        if rp.exists():
            return rp.read_text().strip()
        packed = path / ".git" / "packed-refs"
        if packed.exists():
            for line in packed.read_text().splitlines():
                if line.endswith(ref.split(" ", 1)[1]):
                    return line.split(" ")[0]
        return None
    return ref


def env_info() -> dict:
    import platform

    info = {"python": sys.version.split()[0], "platform": platform.platform()}
    try:
        import torch

        info["torch"] = torch.__version__
        info["cuda"] = torch.version.cuda
        if torch.cuda.is_available():
            info["gpu"] = torch.cuda.get_device_name(0)
    except ImportError:
        pass
    for mod in ("diffusers", "transformers", "trimesh", "rembg", "skimage", "kiwipiepy"):
        try:
            info[mod] = __import__(mod).__version__
        except Exception:
            pass
    return info


class VramPeak:
    """torch가 잡은 VRAM 최대치(GiB). 같은 프로세스 안의 torch 할당만 잰다(Ollama 등 다른 프로세스는 빠짐)."""

    def __enter__(self):
        import torch

        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        return self

    def __exit__(self, *exc):
        import torch

        torch.cuda.synchronize()
        self.allocated_gib = round(torch.cuda.max_memory_allocated() / 2**30, 3)
        self.reserved_gib = round(torch.cuda.max_memory_reserved() / 2**30, 3)
        return False


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))
