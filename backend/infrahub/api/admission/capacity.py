from __future__ import annotations


def derive_max_concurrency(pool_size: int, factor: float) -> int:
    """Derive the per-worker admission slot cap from a real per-process capacity signal.

    The cap is scaled from the database connection pool size rather than a hard-coded
    constant, so it tracks the resources the process actually owns.

    Args:
        pool_size: Number of connections in the process's database pool.
        factor: Multiplier applied to ``pool_size``.

    Returns:
        The slot cap, floored at ``1`` so a pool/factor product below one still
        admits a single request at a time.

    """
    return max(1, int(pool_size * factor))
