import type { components } from "@/shared/api/rest/types.generated";

import type { ArtifactEncryption } from "@/entities/artifacts/domain/model/artifact";

type UnreadableReason = components["schemas"]["UnreadableReason"];

export type ArtifactEncryptionNotice =
  | { level: "success"; message: string }
  | { level: "warning"; message: string }
  | { level: "error"; message: string };

// A missing file has its own notice, so it is the only reason of the API without a text here.
const UNREADABLE_REASONS: Record<Exclude<UnreadableReason, "missing">, string> = {
  unknown_key: "It was not encrypted with the current key.",
  no_key: "No encryption key is configured.",
  unsupported_format: "The file is in a format this version cannot read.",
  truncated: "The file is incomplete.",
};

export interface GetArtifactEncryptionNoticeParams {
  encryption: ArtifactEncryption | null | undefined;
  reason?: UnreadableReason | null;
  isEncryptionEnabled: boolean;
  /** Whether the encryption was found by a check of the file just now, not read from the stored value. */
  isVerified: boolean;
}

export function getArtifactEncryptionNotice({
  encryption,
  reason,
  isEncryptionEnabled,
  isVerified,
}: GetArtifactEncryptionNoticeParams): ArtifactEncryptionNotice | null {
  // A missing file says nothing about its encryption: only an artifact already known as unreadable has a notice.
  if (reason === "missing") {
    return encryption === "unreadable"
      ? { level: "error", message: "The file of this artifact is missing from the storage." }
      : null;
  }

  if (encryption === "unreadable") {
    const detail = reason ? UNREADABLE_REASONS[reason] : undefined;
    return {
      level: "error",
      message:
        `This artifact is encrypted but cannot be read with the current encryption key. ${detail ?? ""}`.trim(),
    };
  }

  if (encryption === "plaintext" && isEncryptionEnabled) {
    return {
      level: "warning",
      message:
        "This artifact is stored without encryption. Encryption only applies to artifacts stored after it was enabled.",
    };
  }

  // The stored value can be out of date, so only a check of the file can say it is still readable.
  if (encryption === "encrypted" && isVerified) {
    return { level: "success", message: "This artifact is encrypted." };
  }

  return null;
}
