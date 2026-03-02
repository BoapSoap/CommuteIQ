import json
import subprocess
from pathlib import Path

from .structural import Settings

MIN_EXPECTED_NEIGHBORHOODS = 10


def _has_usable_acs_file(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return isinstance(payload, dict) and len(payload) >= MIN_EXPECTED_NEIGHBORHOODS


def maybe_build_acs_on_startup(settings: Settings) -> bool:
    """Optionally run ACS preprocessing once before API serves requests.

    Returns True if a build command was executed, else False.
    """
    if not settings.auto_build_acs_on_startup:
        return False

    data_path = settings.data_path
    if not settings.acs_build_force and _has_usable_acs_file(data_path):
        return False

    backend_dir = Path(__file__).resolve().parent.parent

    try:
        subprocess.run(
            ["python3", "scripts/build_acs_neighborhoods.py"],
            cwd=str(backend_dir),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        detail = stderr or stdout or str(exc)
        raise RuntimeError(f"ACS startup build failed: {detail}") from exc

    return True
