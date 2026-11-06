/** Longer than any table cell can show; the cell truncates the rest with an ellipsis. */
const JSON_PREVIEW_MAX_LENGTH = 200;

/** The start of a JSON value on one line, with a space after each separator. */
export function getJsonPreview(value: unknown): string {
  return (JSON.stringify(value, null, 1) ?? "null")
    .replace(/\n\s*/g, " ")
    .slice(0, JSON_PREVIEW_MAX_LENGTH);
}
