"""저장소 경로. shared/ 위치는 환경변수 IFS_SHARED_DIR로 바꿀 수 있다."""
from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
CHATBOT_DIR = PACKAGE_DIR.parent
REPO_ROOT = CHATBOT_DIR.parent
SHARED_DIR = Path(os.environ.get("IFS_SHARED_DIR", REPO_ROOT / "shared")).resolve()
PROMPTS_DIR = CHATBOT_DIR / "prompts"
CONFIG_DIR = CHATBOT_DIR / "config"
SCENARIO_DIR = CHATBOT_DIR / "scenarios"
WEB_DIR = PACKAGE_DIR / "web"


def shared(*parts: str) -> Path:
    return SHARED_DIR.joinpath(*parts)
