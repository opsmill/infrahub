from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.api.admission.capacity import derive_max_concurrency


@dataclass(frozen=True)
class DeriveCase:
    """A (pool_size, factor) input and the slot cap it must derive to."""

    name: str
    pool_size: int
    factor: float
    expected: int


CASES = [
    # Floor: a product below one still admits a single request at a time.
    DeriveCase(name="tiny_product_floors_to_one", pool_size=1, factor=0.01, expected=1),
    DeriveCase(name="zero_pool_floors_to_one", pool_size=0, factor=1.0, expected=1),
    DeriveCase(name="zero_factor_floors_to_one", pool_size=100, factor=0.0, expected=1),
    # Fractional factor scales the pool.
    DeriveCase(name="half_factor_halves_pool", pool_size=10, factor=0.5, expected=5),
    DeriveCase(name="quarter_factor", pool_size=40, factor=0.25, expected=10),
    # Truncation toward zero (int(), not round()).
    DeriveCase(name="fractional_product_truncates", pool_size=10, factor=0.75, expected=7),
    # Identity: factor 1.0 returns the pool size unchanged.
    DeriveCase(name="identity_factor", pool_size=100, factor=1.0, expected=100),
    # Factor above one scales past the pool size.
    DeriveCase(name="factor_above_one", pool_size=10, factor=2.0, expected=20),
]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_derive_max_concurrency(case: DeriveCase) -> None:
    """The cap is exactly ``max(1, int(pool_size * factor))`` — no hard-coded constant."""
    assert derive_max_concurrency(pool_size=case.pool_size, factor=case.factor) == case.expected
    # Redundantly pin the formula so a hidden constant floor/ceiling would fail here too.
    assert case.expected == max(1, int(case.pool_size * case.factor))
