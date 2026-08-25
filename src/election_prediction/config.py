"""Local configuration loading (.env), without adding a dependency.

Credentials are read from the process environment so nothing secret is ever written
to a manifest, report, or the repo. For local runs the project keeps them in a
git-ignored ``.env``; this loader copies them into ``os.environ`` at CLI start-up.

Deliberately dependency-free: CLAUDE.md §7 requires a new dependency to be recorded
with its license before use, and a ~30-line parser is not worth that. Values are
never logged — ``load_dotenv`` returns variable *names* only.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

DEFAULT_ENV_FILE = ".env"

# Names that must never be committed or printed. Used only to decide whether to warn
# loudly when a .env holding them is not ignored by git.
SECRETISH = ("KEY", "TOKEN", "SECRET", "PWD", "PASSWORD", "CREDENTIAL")


def _parse_line(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[len("export ") :].lstrip()
    if "=" not in line:
        return None
    name, _, value = line.partition("=")
    name = name.strip()
    if not name.isidentifier():
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return name, value


def _is_git_ignored(path: Path) -> bool:
    try:
        return (
            subprocess.run(  # noqa: S603 - fixed argv, no shell
                ["git", "check-ignore", "-q", str(path)],
                cwd=path.parent,
                capture_output=True,
                timeout=10,
            ).returncode
            == 0
        )
    except (OSError, subprocess.SubprocessError):
        return False


def load_dotenv(
    path: str | Path = DEFAULT_ENV_FILE, *, override: bool = False, warn: bool = True
) -> list[str]:
    """Load ``KEY=VALUE`` pairs from ``path`` into ``os.environ``.

    Existing environment variables win unless ``override`` is set, so an explicit
    ``export`` in the shell or a CI secret always beats the local file. Returns the
    names that were loaded — never the values.
    """
    env_path = Path(path)
    if not env_path.is_file():
        return []

    if warn and any(s in n.upper() for n in _peek_names(env_path) for s in SECRETISH):
        if not _is_git_ignored(env_path.resolve()):
            print(
                f"  ! {env_path} holds credentials but is NOT git-ignored. "
                "Add it to .gitignore before committing anything.",
                file=sys.stderr,
            )

    loaded = []
    for raw in env_path.read_text().splitlines():
        parsed = _parse_line(raw)
        if parsed is None:
            continue
        name, value = parsed
        if override or name not in os.environ:
            os.environ[name] = value
        loaded.append(name)
    return loaded


def _peek_names(env_path: Path) -> list[str]:
    names = []
    for raw in env_path.read_text().splitlines():
        parsed = _parse_line(raw)
        if parsed is not None:
            names.append(parsed[0])
    return names
