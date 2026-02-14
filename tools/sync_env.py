#!/usr/bin/env python3
"""
One-command environment sync for new machines / cloud runners.

Usage:
    python3 tools/sync_env.py
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict


ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT_DIR / ".env"
ENV_EXAMPLE_FILE = ROOT_DIR / ".env.example"

PLACEHOLDER_PREFIXES = (
    "your_",
    "<",
)
PLACEHOLDER_SUFFIXES = (
    "_here",
    ">",
)
PLACEHOLDER_CONTAINS = (
    "example",
    "replace",
    "changeme",
)


def _log(msg: str) -> None:
    print(msg)


def _run(cmd: list[str], *, cwd: Path = ROOT_DIR, check: bool = False) -> int:
    _log(f"$ {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(cwd), text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}")
    return proc.returncode


def _looks_placeholder(value: str) -> bool:
    norm = value.strip().strip('"').strip("'").lower()
    if not norm:
        return True
    if any(norm.startswith(p) for p in PLACEHOLDER_PREFIXES):
        return True
    if any(norm.endswith(s) for s in PLACEHOLDER_SUFFIXES):
        return True
    if any(chunk in norm for chunk in PLACEHOLDER_CONTAINS):
        return True
    return False


def ensure_env_file() -> None:
    if ENV_FILE.exists():
        _log("[ok] .env already exists")
        return

    if ENV_EXAMPLE_FILE.exists():
        ENV_FILE.write_text(ENV_EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        _log("[ok] .env created from .env.example")
        return

    ENV_FILE.write_text("", encoding="utf-8")
    _log("[warn] .env.example not found, created empty .env")


def parse_env(path: Path) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if not path.exists():
        return result

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def upsert_env_value(path: Path, key: str, value: str) -> None:
    line_to_write = f"{key}={value}\n"
    lines: list[str]

    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    else:
        lines = []

    updated = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"#{key}=") or stripped.startswith(f"# {key}="):
            lines[idx] = line_to_write
            updated = True
            break

    if not updated:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(f"\n{line_to_write}")

    path.write_text("".join(lines), encoding="utf-8")


def _find_service_account_file() -> Path | None:
    candidates = [
        ROOT_DIR / "credentials" / "service_account.json",
        ROOT_DIR / "service_account.json",
        ROOT_DIR / "credentials" / "secret_creds" / "service_account.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def _to_portable_path(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(ROOT_DIR.resolve())
        return rel.as_posix()
    except ValueError:
        return str(path.resolve())


def ensure_credentials_reference() -> bool:
    env = parse_env(ENV_FILE)

    zip_name = (env.get("CREDENTIALS_ZIP_NAME", "secret_creds.zip") or "secret_creds.zip").strip()
    zip_password = (env.get("CREDENTIALS_ZIP_PASSWORD", "") or "").strip()
    zip_path = ROOT_DIR / zip_name
    zip_ok = zip_path.exists() and zip_password and not _looks_placeholder(zip_password)

    creds_file = (env.get("GOOGLE_CREDENTIALS_FILE", "") or "").strip()
    json_ok = False
    if creds_file and not _looks_placeholder(creds_file):
        creds_path = Path(creds_file)
        if not creds_path.is_absolute():
            creds_path = (ROOT_DIR / creds_path).resolve()
        json_ok = creds_path.exists()

    if zip_ok or json_ok:
        _log("[ok] credentials source is configured")
        return True

    found = _find_service_account_file()
    if not found:
        _log("[warn] service_account.json not found in standard locations")
        return False

    portable = _to_portable_path(found)
    upsert_env_value(ENV_FILE, "GOOGLE_CREDENTIALS_FILE", portable)
    _log(f"[ok] GOOGLE_CREDENTIALS_FILE set to: {portable}")
    return True


def install_deps(skip_install: bool) -> bool:
    if skip_install:
        _log("[skip] dependency installation")
        return True

    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-r",
        "requirements.txt",
        "supabase",
        "keyrings.alt",
    ]
    return _run(cmd, cwd=ROOT_DIR) == 0


def smoke_check(*, run_doctor: bool) -> bool:
    ok = True
    if _run([sys.executable, "-c", "import config; print('config import: OK')"], cwd=ROOT_DIR) != 0:
        ok = False

    if run_doctor:
        if _run([sys.executable, "-m", "tools.doctor", "-o", "diagnostics_report.json"], cwd=ROOT_DIR) != 0:
            ok = False
    else:
        _log("[skip] doctor check (use --doctor to enable)")

    return ok


def print_sync_hints() -> None:
    _log("")
    _log("If this machine still differs from your VS Code setup, sync these files manually:")
    _log("  - .env")
    _log("  - credentials/service_account.json  (or secret_creds.zip + CREDENTIALS_ZIP_PASSWORD)")
    _log("")
    _log("Then run:")
    _log("  python3 tools/sync_env.py --strict --doctor")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronize local/cloud environment for WorkTimeTracker in one command."
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip pip install step.",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run tools.doctor after smoke import.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero status if any sync step is incomplete.",
    )
    args = parser.parse_args()

    _log("== WorkTimeTracker environment sync ==")
    ensure_env_file()

    install_ok = install_deps(skip_install=args.skip_install)
    creds_ok = ensure_credentials_reference()
    smoke_ok = smoke_check(run_doctor=args.doctor)

    _log("")
    _log("Summary:")
    _log(f"  dependencies: {'ok' if install_ok else 'failed'}")
    _log(f"  credentials:  {'ok' if creds_ok else 'missing'}")
    _log(f"  smoke check:  {'ok' if smoke_ok else 'failed'}")

    all_ok = install_ok and creds_ok and smoke_ok
    if all_ok:
        _log("")
        _log("Environment sync completed successfully.")
        return 0

    print_sync_hints()
    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
