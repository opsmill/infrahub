import type { components } from "@/shared/api/rest/types.generated";

import type { ArtifactEncryption } from "@/entities/artifacts/domain/model/artifact";

type CheckReason = components["schemas"]["UnreadableReason"];

export type ArtifactUnreadableReason = Exclude<CheckReason, "missing">;

export type ArtifactEncryptionState =
  | { state: "plaintext" }
  | { state: "encrypted" }
  | { state: "unreadable"; reason: ArtifactUnreadableReason | null }
  | { state: "missing" };

export interface GetArtifactEncryptionStateParams {
  encryption: ArtifactEncryption | null | undefined;
  reason?: CheckReason | null;
  isEncryptionEnabled: boolean;
  /** Whether the encryption was found by a check of the file just now, not read from the stored value. */
  isVerified: boolean;
}

export function getArtifactEncryptionState({
  encryption,
  reason,
  isEncryptionEnabled,
  isVerified,
}: GetArtifactEncryptionStateParams): ArtifactEncryptionState | null {
  // A missing file says nothing about its encryption.
  if (reason === "missing") {
    return encryption === "unreadable" ? { state: "missing" } : null;
  }

  if (encryption === "unreadable") return { state: "unreadable", reason: reason ?? null };

  if (encryption === "plaintext" && isEncryptionEnabled) return { state: "plaintext" };

  // The stored value can be out of date, so only a check of the file can say it is still readable.
  if (encryption === "encrypted" && isVerified) return { state: "encrypted" };

  return null;
}
