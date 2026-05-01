"""Pet species assignment is deterministic and tier-weighted."""
from __future__ import annotations

from collections import Counter

import pytest

from app.services import pet_assignment


def test_same_fingerprint_yields_same_species():
    a = pet_assignment.assign_species("1.2.3.4", "Mozilla/5.0 Chrome/120")
    b = pet_assignment.assign_species("1.2.3.4", "Mozilla/5.0 Chrome/120")
    assert a == b


def test_different_ip_changes_species_distribution():
    """Smoke check: spread across 200 IPs hits more than one species."""
    seen = {pet_assignment.assign_species(f"10.0.0.{i}", "ua") for i in range(200)}
    assert len(seen) >= 5  # we have 27 species; should cover several


def test_different_user_agent_changes_species_distribution():
    seen = {pet_assignment.assign_species("1.2.3.4", f"ua-{i}") for i in range(200)}
    assert len(seen) >= 5


def test_assigned_species_is_always_in_catalog():
    catalog = {s for pool in pet_assignment.SPECIES_BY_RARITY.values() for s in pool}
    for i in range(500):
        s = pet_assignment.assign_species(f"10.0.{i // 256}.{i % 256}", "ua")
        assert s in catalog


def test_empty_user_agent_is_fine():
    s1 = pet_assignment.assign_species("1.2.3.4", None)
    s2 = pet_assignment.assign_species("1.2.3.4", "")
    catalog = {s for pool in pet_assignment.SPECIES_BY_RARITY.values() for s in pool}
    assert s1 in catalog
    assert s2 in catalog
    assert s1 == s2  # both normalize to ""


@pytest.mark.parametrize("trials", [5000])
def test_tier_distribution_roughly_matches_weights(trials):
    """Over many random fingerprints, tier frequency tracks RARITY_WEIGHT."""
    counts: Counter[str] = Counter()
    species_to_tier = {
        s: tier for tier, pool in pet_assignment.SPECIES_BY_RARITY.items() for s in pool
    }
    for i in range(trials):
        s = pet_assignment.assign_species(f"10.{i // 65536}.{(i // 256) % 256}.{i % 256}", "ua")
        counts[species_to_tier[s]] += 1

    total_weight = sum(pet_assignment.RARITY_WEIGHT.values())
    for tier, weight in pet_assignment.RARITY_WEIGHT.items():
        expected_frac = weight / total_weight
        observed_frac = counts[tier] / trials
        # Generous bound — we just want to catch obvious skew, not assert
        # exact percentages on a 5000-sample run.
        assert abs(observed_frac - expected_frac) < 0.05, (
            f"{tier}: expected ~{expected_frac:.2%}, got {observed_frac:.2%}"
        )
