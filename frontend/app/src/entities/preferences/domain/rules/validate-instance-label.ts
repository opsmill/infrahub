import { INSTANCE_LABEL_MAX_LENGTH } from "@/entities/preferences/domain/model/instance-identity";

// Line breaks and tabs are in the Cc category; U+202A to U+202E and U+2066 to U+2069 are the
// bidirectional text controls, which can reorder how the label reads.
const CONTROL_CHARACTER = /[\p{Cc}\u202A-\u202E\u2066-\u2069]/u;

export function normalizeInstanceLabel(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

function codePointLength(label: string): number {
  return Array.from(label).length;
}

/** Length of the normalized label in code points, as the server counts it. */
export function instanceLabelLength(value: string): number {
  return codePointLength(normalizeInstanceLabel(value) ?? "");
}

/** Validates the normalized label, as the server does, so a trailing tab is removed rather than rejected. */
export function instanceLabelError(value: string): string | null {
  const label = normalizeInstanceLabel(value) ?? "";
  if (CONTROL_CHARACTER.test(label)) {
    return "The instance label cannot contain control characters.";
  }
  if (codePointLength(label) > INSTANCE_LABEL_MAX_LENGTH) {
    return `The instance label cannot be longer than ${INSTANCE_LABEL_MAX_LENGTH} characters.`;
  }
  return null;
}
