import { describe, expect, test } from "vitest";

import {
  type GetArtifactEncryptionNoticeParams,
  getArtifactEncryptionNotice,
} from "@/entities/artifacts/domain/rules/get-artifact-encryption-notice";

interface Case {
  name: string;
  params: GetArtifactEncryptionNoticeParams;
  expected: ReturnType<typeof getArtifactEncryptionNotice>;
}

const cases: Array<Case> = [
  {
    name: "warns about a plaintext file while encryption is enabled",
    params: { encryption: "plaintext", isEncryptionEnabled: true, isVerified: true },
    expected: {
      level: "warning",
      message:
        "This artifact is stored without encryption. Encryption only applies to artifacts stored after it was enabled.",
    },
  },
  {
    name: "says nothing about a plaintext file while encryption is disabled",
    params: { encryption: "plaintext", isEncryptionEnabled: false, isVerified: true },
    expected: null,
  },
  {
    name: "reassures about an encrypted file that can be read",
    params: { encryption: "encrypted", isEncryptionEnabled: true, isVerified: true },
    expected: { level: "success", message: "This artifact is encrypted." },
  },
  {
    name: "reassures about an encrypted file even when encryption is disabled",
    params: { encryption: "encrypted", isEncryptionEnabled: false, isVerified: true },
    expected: { level: "success", message: "This artifact is encrypted." },
  },
  {
    name: "reports an unreadable file with the reason of the check",
    params: {
      encryption: "unreadable",
      reason: "unknown_key",
      isEncryptionEnabled: true,
      isVerified: true,
    },
    expected: {
      level: "error",
      message:
        "This artifact is encrypted but cannot be read with the current encryption key. It was not encrypted with the current key.",
    },
  },
  {
    name: "reports an unreadable file without a reason before the check answers",
    params: { encryption: "unreadable", isEncryptionEnabled: true, isVerified: true },
    expected: {
      level: "error",
      message: "This artifact is encrypted but cannot be read with the current encryption key.",
    },
  },
  {
    name: "reports an unreadable file even when encryption is disabled",
    params: {
      encryption: "unreadable",
      reason: "no_key",
      isEncryptionEnabled: false,
      isVerified: true,
    },
    expected: {
      level: "error",
      message:
        "This artifact is encrypted but cannot be read with the current encryption key. No encryption key is configured.",
    },
  },
  {
    name: "does not reassure about an encrypted file that no check has confirmed",
    params: { encryption: "encrypted", isEncryptionEnabled: true, isVerified: false },
    expected: null,
  },
  {
    name: "says nothing when the artifact has no encryption value",
    params: { encryption: undefined, isEncryptionEnabled: true, isVerified: true },
    expected: null,
  },
];

describe("getArtifactEncryptionNotice", () => {
  test.each(cases)("$name", ({ params, expected }) => {
    expect(getArtifactEncryptionNotice(params)).toEqual(expected);
  });
});
