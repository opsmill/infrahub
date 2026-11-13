import { afterEach, describe, expect, test, vi } from "vitest";

import { render } from "../../../../tests/components/render";

vi.mock("@/entities/config/ui/queries/get-app-info.query", () => ({
  useGetAppInfo: vi.fn(),
}));
vi.mock("@/entities/artifacts/ui/queries/check-artifact-encryption.query", () => ({
  useCheckArtifactEncryption: vi.fn(),
}));

import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";

import type { ArtifactObject } from "@/entities/artifacts/domain/model/artifact";
import { ArtifactEncryptionBadge } from "@/entities/artifacts/ui/artifact-encryption-badge";
import { useCheckArtifactEncryption } from "@/entities/artifacts/ui/queries/check-artifact-encryption.query";
import { useGetAppInfo } from "@/entities/config/ui/queries/get-app-info.query";

const artifact = (encryption: "plaintext" | "encrypted" | "unreadable") =>
  ({ id: "artifact-1", encryption: { value: encryption } }) as unknown as ArtifactObject;

const appInfo = () =>
  ({
    data: { version: "1.13.0", deployment_id: "d", storage_encryption_enabled: true },
  }) as unknown as ReturnType<typeof useGetAppInfo>;

const check = (data: object | undefined) =>
  ({ data }) as unknown as ReturnType<typeof useCheckArtifactEncryption>;

describe("ArtifactEncryptionBadge", () => {
  afterEach(() => {
    store.set(datetimeAtom, null);
  });

  test("shows the badge when the check confirms that the file is encrypted", async () => {
    // GIVEN
    vi.mocked(useGetAppInfo).mockReturnValue(appInfo());
    vi.mocked(useCheckArtifactEncryption).mockReturnValue(
      check({ encryption: "encrypted", reason: null, updated: false })
    );

    // WHEN
    const component = await render(<ArtifactEncryptionBadge artifact={artifact("encrypted")} />);

    // THEN
    await expect.element(component.getByTestId("artifact-encryption-badge")).toBeVisible();
    await expect.element(component.getByText("encrypted")).toBeVisible();
  });

  test("shows no badge for an encrypted value that no check has confirmed", async () => {
    // GIVEN
    vi.mocked(useGetAppInfo).mockReturnValue(appInfo());
    vi.mocked(useCheckArtifactEncryption).mockReturnValue(check(undefined));

    // WHEN
    const component = await render(<ArtifactEncryptionBadge artifact={artifact("encrypted")} />);

    // THEN
    await expect
      .element(component.getByTestId("artifact-encryption-badge"))
      .not.toBeInTheDocument();
  });

  test("shows no badge while a past date is viewed", async () => {
    // GIVEN
    vi.mocked(useGetAppInfo).mockReturnValue(appInfo());
    vi.mocked(useCheckArtifactEncryption).mockReturnValue(check({ encryption: "encrypted" }));
    store.set(datetimeAtom, new Date("2026-01-01T00:00:00Z"));

    // WHEN
    const component = await render(<ArtifactEncryptionBadge artifact={artifact("encrypted")} />);

    // THEN
    await expect
      .element(component.getByTestId("artifact-encryption-badge"))
      .not.toBeInTheDocument();
  });

  test("shows no badge for a plaintext artifact", async () => {
    // GIVEN
    vi.mocked(useGetAppInfo).mockReturnValue(appInfo());
    vi.mocked(useCheckArtifactEncryption).mockReturnValue(
      check({ encryption: "plaintext", reason: null, updated: false })
    );

    // WHEN
    const component = await render(<ArtifactEncryptionBadge artifact={artifact("plaintext")} />);

    // THEN
    await expect
      .element(component.getByTestId("artifact-encryption-badge"))
      .not.toBeInTheDocument();
  });
});
