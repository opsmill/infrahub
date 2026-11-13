// Returns the first message of a REST error body (`{ errors: [{ message }] }`), if it has one.
export function getRestErrorMessage(error: unknown): string | undefined {
  if (typeof error !== "object" || error === null || !("errors" in error)) return;
  if (!Array.isArray(error.errors)) return;

  const first: unknown = error.errors[0];
  if (typeof first !== "object" || first === null || !("message" in first)) return;

  return typeof first.message === "string" && first.message !== "" ? first.message : undefined;
}
