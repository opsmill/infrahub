/** Shows that a secret is set without revealing it, or its length. */
export function MaskedValue() {
  return (
    <span role="img" aria-label="Value set, hidden" className="select-none text-foreground-muted">
      ••••••••
    </span>
  );
}
