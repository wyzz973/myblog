"""Deterministic per-visitor pet species assignment.

Each visitor is tied to one species via HMAC-SHA256 over (ip, user_agent)
keyed by the server-side `like_salt`. Same fingerprint always produces
the same species, so clearing localStorage / cookies / private mode does
NOT re-roll. Different browsers or networks DO re-roll, by design.

Tier weights mirror the previous client-side roll (common 50, uncommon 25,
rare 15, epic 7, legendary 3) so spotting a legendary still feels rare.

The species catalog is server-side state of the world: must stay in sync
with `src/components/pet/species.js` on the frontend (same names, same
rarity tiers). The frontend renders the sprite — the server only picks
the key.
"""
from __future__ import annotations

import hashlib
import hmac

from app.config import get_settings

RARITY_WEIGHT: dict[str, int] = {
    "common":    50,
    "uncommon":  25,
    "rare":      15,
    "epic":      7,
    "legendary": 3,
}

# Mirrors src/components/pet/species.js. Update both files together when
# the catalog changes.
SPECIES_BY_RARITY: dict[str, list[str]] = {
    "common":    ["duck", "goose", "blob", "cat", "rabbit"],
    "uncommon":  ["penguin", "owl", "turtle", "capybara"],
    "rare":      ["mushroom", "ghost", "snail", "cactus", "chonk"],
    "epic":      ["octopus", "jellyfish", "axolotl", "robot"],
    "legendary": ["dragon", "phoenix", "fox", "shiba", "mochi",
                  "panda", "hamster", "bee", "otter"],
}

DEFAULT_SPECIES = "cat"


def _stable_hash(ip: str, user_agent: str) -> int:
    """64-bit unsigned int derived from (ip, user_agent) via HMAC-SHA256."""
    salt = get_settings().like_salt.encode()
    msg = f"{ip}|{user_agent}".encode()
    digest = hmac.new(salt, msg, hashlib.sha256).digest()
    return int.from_bytes(digest[:8], "big")


def assign_species(ip: str, user_agent: str | None) -> str:
    """Return the species key this fingerprint should always get.

    Deterministic: same (ip, ua) → same species. Different inputs roll
    independently (so changing browser or IP changes the result).
    """
    ua = user_agent or ""
    h = _stable_hash(ip, ua)

    total_weight = sum(RARITY_WEIGHT.values())
    tier_roll = h % total_weight  # 0 .. total_weight-1
    acc = 0
    chosen_tier = "common"
    for tier, weight in RARITY_WEIGHT.items():
        acc += weight
        if tier_roll < acc:
            chosen_tier = tier
            break

    pool = SPECIES_BY_RARITY.get(chosen_tier) or []
    if not pool:
        return DEFAULT_SPECIES
    # Use a different slice of the same hash for within-tier selection so
    # the tier roll and the within-tier roll aren't perfectly correlated.
    inner_roll = (h >> 32) % len(pool)
    return pool[inner_roll]
