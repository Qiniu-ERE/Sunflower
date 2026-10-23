"""Profile + secrets loading. Hardware differences live only in profiles/*.json."""
import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOME = pathlib.Path(os.environ.get("SUNFLOWER_HOME", pathlib.Path.home() / ".sunflower"))


def load_env(path=None):
    path = pathlib.Path(path or ROOT / ".env")
    env = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if k.startswith(("LINX_", "SUNFLOWER_"))})
    return env


def load_profile(name_or_path):
    p = pathlib.Path(name_or_path)
    if not p.suffix:
        p = ROOT / "profiles" / f"{name_or_path}.json"
    if not p.exists():
        raise SystemExit(f"profile not found: {p} (available: "
                         f"{', '.join(x.stem for x in (ROOT / 'profiles').glob('*.json'))})")
    prof = json.loads(p.read_text(encoding="utf-8"))
    prof.setdefault("name", p.stem)
    return prof


def state_path(name):
    HOME.mkdir(parents=True, exist_ok=True)
    return HOME / name


def read_state(name, default=None):
    p = state_path(name)
    if not p.exists():
        return {} if default is None else default
    return json.loads(p.read_text(encoding="utf-8"))


def write_state(name, data):
    p = state_path(name)
    tmp = p.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)
