import { INSTANCE_LABEL_MAX_LENGTH } from "@/entities/preferences/domain/model/instance-identity";

const LINE_BREAK = /[\n\r]/;

export function normalizeInstanceLabel(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

export function instanceLabelError(value: string): string | null {
  if (LINE_BREAK.test(value)) {
    return "The instance label cannot contain a line break.";
  }
  if (value.trim().length > INSTANCE_LABEL_MAX_LENGTH) {
    return `The instance label cannot be longer than ${INSTANCE_LABEL_MAX_LENGTH} characters.`;
  }
  return null;
}
