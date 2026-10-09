export function getRepositoryLocation({ location }: Record<string, unknown>): string | null {
  return location &&
    typeof location === "object" &&
    "value" in location &&
    typeof location.value === "string"
    ? location.value
    : null;
}
