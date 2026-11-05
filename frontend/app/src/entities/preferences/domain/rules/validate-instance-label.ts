import { INSTANCE_LABEL_MAX_LENGTH } from "@/entities/preferences/domain/model/instance-identity";

// Line breaks and tabs are in the Cc category; U+202A–U+202E and U+2066–U+2069 are the
// bidirectional text controls, which can reorder how the label reads.
const CONTROL_CHARACTER = /[\p{Cc}‪-‮⁦-⁩]/u;

export function normalizeInstanceLabel(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

/** Length of the trimmed label in code points, as the server counts it. */
export function instanceLabelLength(value: string): number {
  return Array.from(value.trim()).length;
}

export function instanceLabelError(value: string): string | null {
  if (CONTROL_CHARACTER.test(value)) {
    return "The instance label cannot contain control characters.";
  }
  if (instanceLabelLength(value) > INSTANCE_LABEL_MAX_LENGTH) {
    return `The instance label cannot be longer than ${INSTANCE_LABEL_MAX_LENGTH} characters.`;
  }
  return null;
}
