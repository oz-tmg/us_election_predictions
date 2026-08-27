"""Governed acquisition helpers — fetch, verify, checksum.

Every raw snapshot in this project must be an *exact, verified* copy of what the
source published (docs/ingestion-playbook.md Step 2; CLAUDE.md §4). Two failure
modes motivated this module, both observed against the real endpoints:

1. **HTTP 200 with an error body.** The Census API returns a ``200`` and an HTML
   "Missing Key" page when no API key is supplied. Writing that page into
   ``data/raw/`` and checksumming it would produce a manifest that certifies an
   error page as data.
2. **Gated sources.** Some Harvard Dataverse datasets sit behind a *guestbook*
   that the access API refuses to satisfy. Silently falling back to a synthetic
   fixture there would let a build report success while modelling fiction.

So downloads are written to a temporary file, sniffed and validated, and only then
moved into the raw snapshot path. Anything unexpected raises rather than lands.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

USER_AGENT = "election-prediction/0.0.1 (nonpartisan research; contact: project owner)"

# How many bytes to sniff when deciding whether a response body is real data.
_SNIFF = 4096


class AcquisitionError(RuntimeError):
    """Base class for every acquisition failure."""


class NetworkUnavailable(AcquisitionError):
    """The endpoint could not be reached at all (offline sandbox, DNS, timeout)."""


class InvalidResponse(AcquisitionError):
    """The endpoint answered, but the body is not the dataset we asked for."""


class CredentialRequired(AcquisitionError):
    """The source needs an API key/credential that is not configured.

    Kept distinct from ``InvalidResponse`` because the fix is operator configuration,
    not a code or endpoint problem.
    """

    def __init__(self, message: str, *, env_var: str, signup_url: str):
        super().__init__(message)
        self.env_var = env_var
        self.signup_url = signup_url

    def instructions(self) -> str:
        return "\n".join(
            [
                str(self),
                "",
                f"    1. Request a key at {self.signup_url}",
                f"    2. Export it:  export {self.env_var}=<your key>",
                "    3. Re-run the build.",
            ]
        )


class ManualAcquisitionRequired(AcquisitionError):
    """The source is gated (guestbook/login) and cannot be fetched programmatically.

    Carries operator-facing instructions so the build prints exactly what a human
    must do to land the snapshot, rather than degrading to synthetic data.
    """

    def __init__(
        self,
        message: str,
        *,
        url: str,
        filename: str,
        drop_dir: Path,
        expected_md5: str | None = None,
        expected_size: int | None = None,
    ):
        super().__init__(message)
        self.url = url
        self.filename = filename
        self.drop_dir = Path(drop_dir)
        self.expected_md5 = expected_md5
        self.expected_size = expected_size

    def instructions(self) -> str:
        lines = [
            str(self),
            "",
            "  To land this snapshot (one-time, per source):",
            f"    1. Open {self.url}",
            "    2. Accept the dataset guestbook / terms and download the file.",
            "    3. Save it, unmodified, as:",
            f"         {self.drop_dir / self.filename}",
            "    4. Re-run the build. The checksum is verified before the file is used.",
        ]
        if self.expected_md5:
            lines.append(f"       expected md5:  {self.expected_md5}")
        if self.expected_size:
            lines.append(f"       expected size: {self.expected_size:,} bytes")
        return "\n".join(lines)


# ------------------------------------------------------------------- checksums
def sha256_file(path: str | Path, *, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def md5_file(path: str | Path, *, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()  # noqa: S324 - matching the checksum Dataverse publishes, not a security use
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


# -------------------------------------------------------------- body sniffing
def looks_like_html(head: bytes) -> bool:
    start = head.lstrip()[:512].lower()
    return start.startswith(b"<!doctype html") or start.startswith(b"<html")


def dataverse_error(head: bytes) -> str | None:
    """Return the message if ``head`` is a Dataverse JSON error envelope."""
    stripped = head.lstrip()
    if not stripped.startswith(b"{"):
        return None
    try:
        payload = json.loads(stripped.decode("utf-8", "replace"))
    except ValueError:
        return None
    if isinstance(payload, dict) and payload.get("status") == "ERROR":
        return str(payload.get("message", "unknown Dataverse error"))
    return None


def _validate_body(head: bytes, *, expect: str, url: str) -> None:
    """Raise InvalidResponse if the sniffed body is not the expected kind of data."""
    if not head.strip():
        raise InvalidResponse(f"Empty response body from {url}")

    if (msg := dataverse_error(head)) is not None:
        raise InvalidResponse(f"Dataverse returned an error for {url}: {msg}")

    if expect in {"csv", "tsv", "json"} and looks_like_html(head):
        # The Census API does this: HTTP 200 + an HTML error page.
        title = re.search(rb"<title>(.*?)</title>", head, re.I | re.S)
        detail = title.group(1).decode("utf-8", "replace").strip() if title else "HTML page"
        raise InvalidResponse(
            f"Expected {expect} from {url} but received an HTML page ({detail!r}). "
            "This usually means a missing API key or an expired endpoint."
        )

    if expect == "json":
        stripped = head.lstrip()
        if not stripped.startswith((b"[", b"{")):
            raise InvalidResponse(f"Expected JSON from {url}, got: {stripped[:80]!r}")

    if expect == "zip" and not head.startswith(b"PK"):
        raise InvalidResponse(f"Expected a zip archive from {url}, got: {head[:80]!r}")


# ------------------------------------------------------------------- fetching
def fetch(
    url: str,
    out_path: str | Path,
    *,
    expect: str = "csv",
    timeout: int = 180,
    expected_md5: str | None = None,
    expected_size: int | None = None,
    size_tolerance: float = 0.02,
    headers: dict[str, str] | None = None,
) -> Path:
    """Download ``url`` to ``out_path``, validating before it lands.

    ``expect`` is one of ``csv`` | ``tsv`` | ``json`` | ``zip`` and drives body
    sniffing. The file is written to a ``.part`` sibling and only moved into place
    once it passes validation, so a failed fetch never leaves a half-written or
    error-page "snapshot" behind.

    Raises NetworkUnavailable, InvalidResponse, or AcquisitionError on checksum
    mismatch.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".part")

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed https endpoints
            head = resp.read(_SNIFF)
            _validate_body(head, expect=expect, url=url)
            with open(tmp_path, "wb") as fh:
                fh.write(head)
                while chunk := resp.read(1 << 20):
                    fh.write(chunk)
    except urllib.error.HTTPError as e:
        body = e.read(_SNIFF) if hasattr(e, "read") else b""
        tmp_path.unlink(missing_ok=True)
        if (msg := dataverse_error(body)) is not None:
            raise InvalidResponse(f"{url} -> HTTP {e.code}: {msg}") from e
        raise NetworkUnavailable(f"{url} -> HTTP {e.code} {e.reason}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        tmp_path.unlink(missing_ok=True)
        raise NetworkUnavailable(f"Could not reach {url}: {e}") from e
    except InvalidResponse:
        tmp_path.unlink(missing_ok=True)
        raise

    try:
        verify_file(
            tmp_path,
            expected_md5=expected_md5,
            expected_size=expected_size,
            size_tolerance=size_tolerance,
            url=url,
        )
    except AcquisitionError:
        tmp_path.unlink(missing_ok=True)
        raise

    tmp_path.replace(out_path)
    return out_path


def verify_file(
    path: str | Path,
    *,
    expected_md5: str | None = None,
    expected_size: int | None = None,
    size_tolerance: float = 0.02,
    url: str = "",
) -> None:
    """Check a downloaded/manually-placed file against the source's published metadata.

    Size is checked with a small tolerance because Dataverse re-serves *ingested*
    tabular files with minor formatting differences; md5 is checked exactly when
    the source publishes one for the exact representation we fetch.
    """
    path = Path(path)
    size = path.stat().st_size
    where = f" ({url})" if url else ""

    if expected_size is not None and size_tolerance is not None:
        low = expected_size * (1 - size_tolerance)
        high = expected_size * (1 + size_tolerance)
        if not (low <= size <= high):
            raise AcquisitionError(
                f"Size mismatch for {path.name}{where}: got {size:,} bytes, "
                f"expected ~{expected_size:,}. The source layout may have changed."
            )

    if expected_md5:
        actual = md5_file(path)
        if actual != expected_md5:
            raise AcquisitionError(
                f"Checksum mismatch for {path.name}{where}: md5 {actual} != "
                f"expected {expected_md5}. Refusing to use an unverified snapshot."
            )
