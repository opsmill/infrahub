def raise_needs_rebase_error(branch_name: str) -> None:
    raise ValueError(f"Branch {branch_name} must be rebased before any updates can be made")
