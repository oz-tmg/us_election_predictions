"""Data classification tiers and guardrails.

Single source of truth for the privacy tiers defined in CLAUDE.md §5 and
docs/data-governance-and-privacy.md. Every dataset that enters the modeling
layer carries a tier; ingestion refuses to land Tier 3+ data in the public lake.
"""

from __future__ import annotations

from enum import IntEnum


class PrivacyTier(IntEnum):
    """Escalating sensitivity. Higher = more restricted (CLAUDE.md §5)."""

    PUBLIC_AGGREGATE = 0  # certified returns, ACS tables, TIGER boundaries
    PUBLIC_SENSITIVE_AGGREGATE = 1  # precinct returns, small-area demographics
    PUBLIC_PERSONAL = 2  # FEC itemized donors, some voter-file fields
    LICENSED_PERSONAL = 3  # state/national voter files, consumer append
    CAMPAIGN_OPERATIONAL = 4  # VAN/CRM exports, canvass, persuasion surveys
    DERIVED_SENSITIVE = 5  # modeled partisanship, turnout/support scores

    @property
    def label(self) -> str:
        return {
            0: "public_aggregate",
            1: "public_sensitive_aggregate",
            2: "public_personal",
            3: "licensed_personal",
            4: "campaign_operational",
            5: "derived_sensitive",
        }[int(self)]

    @property
    def may_enter_public_repo(self) -> bool:
        """Tier 0-2 may be used in the public project (with rules). Tier 3+ never."""
        return int(self) <= 2


# The public project only ingests Tier 0-2. Anything higher must be stopped at
# the door and handled in a private, governed environment.
MAX_PUBLIC_TIER = PrivacyTier.PUBLIC_PERSONAL


class GovernanceError(RuntimeError):
    """Raised when an action would violate a hard governance rule (CLAUDE.md §5)."""


def assert_public_safe(tier: PrivacyTier, *, context: str = "") -> None:
    """Refuse to proceed if ``tier`` is too sensitive for the public repo.

    This is the programmatic form of the §5 rule: *stop and refuse, then propose
    a compliant path.* Callers should catch GovernanceError and route the dataset
    to the private governed store instead.
    """
    if tier > MAX_PUBLIC_TIER:
        raise GovernanceError(
            f"Privacy tier {int(tier)} ({tier.label}) may not enter the public repo"
            + (f" [{context}]" if context else "")
            + ". Store outside the public repo, encrypted, with hashed IDs "
            "(CLAUDE.md §5). Aggregate first, then release only after review."
        )
