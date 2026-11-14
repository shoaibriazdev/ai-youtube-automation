"""Every test run uses a throwaway data + projects folder, never your real ones."""
import os
import sys
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="ytauto_test_"))
os.environ["YTAUTO_DATA_DIR"] = str(_TMP / "data")
os.environ["YTAUTO_PROJECTS_DIR"] = str(_TMP / "projects")
# Never touch real paid APIs from tests, even if the developer has keys in .env
for k in ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "OPENAI_API_KEY", "STABILITY_API_KEY", "REPLICATE_API_TOKEN",
          "RUNWAY_API_KEY", "LUMA_API_KEY", "YOUTUBE_API_KEY", "POLLINATIONS_TOKEN"):
    os.environ[k] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def tmp_root():
    return _TMP


@pytest.fixture()
def free_providers():
    """Free, offline-capable providers + fast draft renders."""
    from ytauto import db
    db.conn()
    db.set_setting("providers", {"llm": "offline", "image": "storyboard", "video": "kenburns", "tts": "silent"})
    r = db.get_setting("render")
    r.update(quality="draft")
    db.set_setting("render", r)
    db.set_setting("costs", {"require_approval_above_usd": 0.0, "monthly_budget_usd": 10.0})
    yield
