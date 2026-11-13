export function getRepositoryInternalStatus({
  internal_status,
}: Record<string, unknown>): string | null {
  return internal_status &&
    typeof internal_status === "object" &&
    "value" in internal_status &&
    typeof internal_status.value === "string"
    ? internal_status.value
    : null;
}
