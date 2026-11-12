"""Cloudflare Access verification for the vault service.

Cloudflare Access sits in front of ``vault.elections.alexoswald.ca`` and adds a signed JWT
(``Cf-Access-Jwt-Assertion``) to every request it lets through. Access alone is not enough:
the Cloud Run service also answers on its ``*.run.app`` URL, which bypasses Cloudflare. So
the vault app verifies the token itself on every request — signature against the team's
published keys, audience against the Access application's AUD tag, issuer against the team
domain — and refuses anything else with 403.

``EP_DASH_INSECURE_LOCAL=1`` disables verification for local development only; it is
refused when ``K_SERVICE`` is set, which Cloud Run sets on every revision.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import jwt

HEADER = "Cf-Access-Jwt-Assertion"
COOKIE = "CF_Authorization"


class AccessDenied(Exception):
    pass


class _SigningKeySource(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> Any: ...


@dataclass
class AccessVerifier:
    team_domain: str
    audience: str
    keys: _SigningKeySource | None = None

    def __post_init__(self) -> None:
        self.team_domain = self.team_domain.removeprefix("https://").rstrip("/")
        if not self.team_domain or not self.audience:
            raise ValueError("Access verification needs a team domain and an AUD tag")
        if self.keys is None:
            self.keys = jwt.PyJWKClient(f"{self.issuer}/cdn-cgi/access/certs", cache_keys=True)

    @property
    def issuer(self) -> str:
        return f"https://{self.team_domain}"

    def verify(self, token: str | None) -> dict[str, Any]:
        """Return the verified claims, or raise ``AccessDenied``."""
        if not token:
            raise AccessDenied("no Cloudflare Access token")
        assert self.keys is not None
        try:
            key = self.keys.get_signing_key_from_jwt(token).key
            return jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "aud", "iss"]},
            )
        except jwt.PyJWTError as exc:
            raise AccessDenied(f"invalid Cloudflare Access token: {exc}") from exc

    def verify_request(self, headers: Any, cookies: Any) -> dict[str, Any]:
        """``headers``/``cookies``: anything with ``.get`` (werkzeug's are not Mappings)."""
        return self.verify(headers.get(HEADER) or cookies.get(COOKIE))


def insecure_local_allowed(env: Mapping[str, str] = os.environ) -> bool:
    if env.get("EP_DASH_INSECURE_LOCAL") != "1":
        return False
    if env.get("K_SERVICE"):
        raise RuntimeError("EP_DASH_INSECURE_LOCAL is refused on Cloud Run (K_SERVICE is set)")
    return True
