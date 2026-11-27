import { describe, expect, test } from "vitest";

import {
  type GetArtifactEncryptionStateParams,
  getArtifactEncryptionState,
} from "@/entities/artifacts/domain/rules/get-artifact-encryption-state";

interface Case {
  name: string;
  params: GetArtifactEncryptionStateParams;
  expected: ReturnType<typeof getArtifactEncryptionState>;
}

const cases: Array<Case> = [
  {
    name: "warns about a plaintext file while encryption is enabled",
    params: { encryption: "plaintext", isEncryptionEnabled: true, isVerified: true },
    expected: { state: "plaintext" },
  },
  {
    name: "says nothing about a plaintext file while encryption is disabled",
    params: { encryption: "plaintext", isEncryptionEnabled: false, isVerified: true },
    expected: null,
  },
  {
    name: "reassures about an encrypted file that can be read",
    params: { encryption: "encrypted", isEncryptionEnabled: true, isVerified: true },
    expected: { state: "encrypted" },
  },
  {
    name: "reassures about an encrypted file even when encryption is disabled",
    params: { encryption: "encrypted", isEncryptionEnabled: false, isVerified: true },
    expected: { state: "encrypted" },
  },
  {
    name: "reports an unreadable file with the reason of the check",
    params: {
      encryption: "unreadable",
      reason: "unknown_key",
      isEncryptionEnabled: true,
      isVerified: true,
    },
    expected: { state: "unreadable", reason: "unknown_key" },
  },
  {
    name: "reports an unreadable file without a reason before the check answers",
    params: { encryption: "unreadable", isEncryptionEnabled: true, isVerified: true },
    expected: { state: "unreadable", reason: null },
  },
  {
    name: "reports an unreadable file even when encryption is disabled",
    params: {
      encryption: "unreadable",
      reason: "no_key",
      isEncryptionEnabled: false,
      isVerified: true,
    },
    expected: { state: "unreadable", reason: "no_key" },
  },
  {
    name: "does not reassure about an encrypted file that no check has confirmed",
    params: { encryption: "encrypted", isEncryptionEnabled: true, isVerified: false },
    expected: null,
  },
  {
    name: "reports an unreadable artifact whose file is missing as a missing file",
    params: {
      encryption: "unreadable",
      reason: "missing",
      isEncryptionEnabled: true,
      isVerified: false,
    },
    expected: { state: "missing" },
  },
  {
    name: "does not warn about a plaintext artifact whose file is missing",
    params: {
      encryption: "plaintext",
      reason: "missing",
      isEncryptionEnabled: true,
      isVerified: false,
    },
    expected: null,
  },
  {
    name: "does not reassure about an encrypted artifact whose file is missing",
    params: {
      encryption: "encrypted",
      reason: "missing",
      isEncryptionEnabled: true,
      isVerified: true,
    },
    expected: null,
  },
  {
    name: "says nothing when the artifact has no encryption value",
    params: { encryption: undefined, isEncryptionEnabled: true, isVerified: true },
    expected: null,
  },
];

describe("getArtifactEncryptionState", () => {
  test.each(cases)("$name", ({ params, expected }) => {
    expect(getArtifactEncryptionState(params)).toEqual(expected);
  });
});
