import { beforeEach, describe, expect, test, vi } from "vitest";

import { render } from "../../../../tests/components/render";

vi.mock("@/entities/config/ui/queries/get-app-info.query", () => ({
  useGetAppInfo: vi.fn(),
}));
vi.mock("@/entities/artifacts/ui/queries/check-artifact-encryption.query", () => ({
  useCheckArtifactEncryption: vi.fn(),
}));

import type { ArtifactObject } from "@/entities/artifacts/domain/model/artifact";
import { ArtifactEncryptionNotice } from "@/entities/artifacts/ui/artifact-encryption-notice";
import { useCheckArtifactEncryption } from "@/entities/artifacts/ui/queries/check-artifact-encryption.query";
import { useGetAppInfo } from "@/entities/config/ui/queries/get-app-info.query";

const artifact = (encryption: "plaintext" | "encrypted" | "unreadable") =>
  ({ id: "artifact-1", encryption: { value: encryption } }) as unknown as ArtifactObject;

const appInfo = (isEnabled: boolean) =>
  ({
    data: { version: "1.13.0", deployment_id: "d", storage_encryption_enabled: isEnabled },
  }) as unknown as ReturnType<typeof useGetAppInfo>;

const check = (data: object | undefined) =>
  ({ data }) as unknown as ReturnType<typeof useCheckArtifactEncryption>;

describe("ArtifactEncryptionNotice", () => {
  beforeEach(() => {
    vi.mocked(useCheckArtifactEncryption).mockReturnValue(check(undefined));
  });

  test("warns when the file is plaintext and encryption is enabled", async () => {
    vi.mocked(useGetAppInfo).mockReturnValue(appInfo(true));

    const component = await render(<ArtifactEncryptionNotice artifact={artifact("plaintext")} />);

    await expect
      .element(component.getByText(/This artifact is stored without encryption/))
      .toBeVisible();
  });

  test("shows nothing when the file is plaintext and encryption is disabled", async () => {
    vi.mocked(useGetAppInfo).mockReturnValue(appInfo(false));

    const component = await render(<ArtifactEncryptionNotice artifact={artifact("plaintext")} />);

    await expect
      .element(component.getByTestId("artifact-encryption-notice"))
      .not.toBeInTheDocument();
  });

  test("reassures when the check confirms that the file is encrypted", async () => {
    vi.mocked(useGetAppInfo).mockReturnValue(appInfo(true));
    vi.mocked(useCheckArtifactEncryption).mockReturnValue(
      check({ encryption: "encrypted", reason: null, updated: false })
    );

    const component = await render(<ArtifactEncryptionNotice artifact={artifact("encrypted")} />);

    await expect.element(component.getByText("This artifact is encrypted.")).toBeVisible();
  });

  test("does not reassure from the stored value when no check answered", async () => {
    vi.mocked(useGetAppInfo).mockReturnValue(appInfo(true));

    const component = await render(<ArtifactEncryptionNotice artifact={artifact("encrypted")} />);

    await expect
      .element(component.getByTestId("artifact-encryption-notice"))
      .not.toBeInTheDocument();
  });

  test("shows an error with the reason when the check finds the file unreadable", async () => {
    vi.mocked(useGetAppInfo).mockReturnValue(appInfo(true));
    vi.mocked(useCheckArtifactEncryption).mockReturnValue(
      check({ encryption: "unreadable", reason: "unknown_key", updated: true })
    );

    const component = await render(<ArtifactEncryptionNotice artifact={artifact("encrypted")} />);

    await expect
      .element(
        component.getByText(
          /cannot be read with the current encryption key. It was not encrypted with the current key./
        )
      )
      .toBeVisible();
  });

  test("the check overrides the stored value", async () => {
    vi.mocked(useGetAppInfo).mockReturnValue(appInfo(true));
    vi.mocked(useCheckArtifactEncryption).mockReturnValue(
      check({ encryption: "encrypted", reason: null, updated: true })
    );

    const component = await render(<ArtifactEncryptionNotice artifact={artifact("unreadable")} />);

    await expect.element(component.getByText("This artifact is encrypted.")).toBeVisible();
  });
});
