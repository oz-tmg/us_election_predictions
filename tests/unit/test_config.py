"""Tests for local .env loading.

Credentials must reach the process environment without ever being written into a
manifest, report, or log line.
"""

from __future__ import annotations

import os

from election_prediction.config import load_dotenv


def test_loads_pairs_and_returns_names_only(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "# a comment\n"
        "\n"
        "CENSUS_API_KEY=abc123\n"
        "export DATAVERSE_API_TOKEN='tok-456'\n"
        'QUOTED="has spaces"\n'
        "NO_TRAILING_NEWLINE=xyz"
    )
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    monkeypatch.delenv("DATAVERSE_API_TOKEN", raising=False)

    loaded = load_dotenv(env, warn=False)

    assert set(loaded) == {"CENSUS_API_KEY", "DATAVERSE_API_TOKEN", "QUOTED", "NO_TRAILING_NEWLINE"}
    assert os.environ["CENSUS_API_KEY"] == "abc123"
    assert os.environ["DATAVERSE_API_TOKEN"] == "tok-456"  # export prefix + quotes stripped
    assert os.environ["QUOTED"] == "has spaces"
    assert os.environ["NO_TRAILING_NEWLINE"] == "xyz"
    # The return value is safe to print: names only, no secret values.
    assert not any("abc123" in name or "tok-456" in name for name in loaded)


def test_existing_environment_wins_by_default(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("CENSUS_API_KEY=from_file\n")
    monkeypatch.setenv("CENSUS_API_KEY", "from_shell")

    load_dotenv(env, warn=False)
    assert os.environ["CENSUS_API_KEY"] == "from_shell"

    load_dotenv(env, override=True, warn=False)
    assert os.environ["CENSUS_API_KEY"] == "from_file"


def test_missing_file_is_not_an_error(tmp_path):
    assert load_dotenv(tmp_path / "nope.env", warn=False) == []


def test_malformed_lines_are_skipped(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("not a pair\n123INVALID=x\nGOOD=1\n")
    monkeypatch.delenv("GOOD", raising=False)
    assert load_dotenv(env, warn=False) == ["GOOD"]


def test_warns_when_secrets_file_is_not_gitignored(tmp_path, capsys):
    """A .env holding credentials outside git's ignore rules must be called out."""
    env = tmp_path / ".env"  # tmp_path is not a git repo -> not ignored
    env.write_text("CENSUS_API_KEY=abc\n")
    load_dotenv(env, warn=True)
    err = capsys.readouterr().err
    assert "NOT git-ignored" in err
    assert "abc" not in err  # the warning must not leak the value
