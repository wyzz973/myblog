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


def test_cookie_round_trip():
    signed = pet_assignment.sign_cookie("panda")
    assert pet_assignment.verify_cookie(signed) == "panda"


def test_cookie_rejects_tampered_hmac():
    signed = pet_assignment.sign_cookie("panda")
    # flip a char in the hmac portion
    bad = signed[:-1] + ("0" if signed[-1] != "0" else "1")
    assert pet_assignment.verify_cookie(bad) is None


def test_cookie_rejects_unknown_species():
    # An attacker who knows the salt could in theory sign their own value,
    # but verify_cookie still rejects species not in the catalog.
    assert pet_assignment.verify_cookie("godzilla|deadbeefdeadbeef") is None


def test_cookie_rejects_malformed():
    assert pet_assignment.verify_cookie(None) is None
    assert pet_assignment.verify_cookie("") is None
    assert pet_assignment.verify_cookie("panda") is None  # no |
    assert pet_assignment.verify_cookie("|abc") is None
    assert pet_assignment.verify_cookie("panda|") is None


def test_cookie_substitution_attack_fails():
    """Attacker takes a legitimate panda cookie and swaps panda → dragon —
    the HMAC was over 'panda', so the value no longer verifies."""
    signed_panda = pet_assignment.sign_cookie("panda")
    _, _, panda_tag = signed_panda.partition("|")
    forged = f"dragon|{panda_tag}"
    assert pet_assignment.verify_cookie(forged) is None


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
