// gql.tada types the DateTime scalar as unknown; the wire carries ISO 8601 strings.
export function toDateTime(value: unknown): string {
  if (typeof value !== "string") {
    throw new Error("Expected an ISO 8601 DateTime string");
  }
  return value;
}

export function toDateTimeOrNull(value: unknown): string | null {
  return value === null || value === undefined ? null : toDateTime(value);
}
