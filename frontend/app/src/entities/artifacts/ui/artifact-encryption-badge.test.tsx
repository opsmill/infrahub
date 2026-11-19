import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { render } from "../../../../tests/components/render";

vi.mock("@/entities/config/ui/queries/get-app-info.query", () => ({
  useGetAppInfo: vi.fn(),
}));
vi.mock("@/entities/artifacts/ui/queries/check-artifact-encryption.query", () => ({
  useCheckArtifactEncryption: vi.fn(),
}));
vi.mock("@/entities/artifacts/api/get-artifact-file-from-api", () => ({
  getArtifactFileFromApi: vi.fn(),
}));

import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { getArtifactFileFromApi } from "@/entities/artifacts/api/get-artifact-file-from-api";
import type { ArtifactObject } from "@/entities/artifacts/domain/model/artifact";
import { ArtifactEncryptionBadge } from "@/entities/artifacts/ui/artifact-encryption-badge";
import { useCheckArtifactEncryption } from "@/entities/artifacts/ui/queries/check-artifact-encryption.query";
import { useGetAppInfo } from "@/entities/config/ui/queries/get-app-info.query";

const artifact = (encryption: "plaintext" | "encrypted" | "unreadable") =>
  ({
    id: "artifact-1",
    encryption: { value: encryption },
    storage_id: { value: "storage-1" },
    content_type: { value: "text/plain" },
  }) as unknown as ArtifactObject;

const contentRequest = (status: number, message: string) =>
  ({
    error: { data: null, errors: [{ message, extensions: { code: status } }] },
    response: { status },
  }) as unknown as Awaited<ReturnType<typeof getArtifactFileFromApi>>;

const appInfo = () =>
  ({
    data: { version: "1.13.0", deployment_id: "d", storage_encryption_enabled: true },
  }) as unknown as ReturnType<typeof useGetAppInfo>;

const check = (data: object | undefined) =>
  ({ data }) as unknown as ReturnType<typeof useCheckArtifactEncryption>;

describe("ArtifactEncryptionBadge", () => {
  beforeEach(() => {
    vi.mocked(getArtifactFileFromApi).mockResolvedValue({
      data: "content",
      response: { status: 200 },
    } as unknown as Awaited<ReturnType<typeof getArtifactFileFromApi>>);
  });

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

  describe("when the content of the artifact cannot be read", () => {
    const confirmedEncrypted = () => {
      vi.mocked(useGetAppInfo).mockReturnValue(appInfo());
      vi.mocked(useCheckArtifactEncryption).mockReturnValue(
        check({ encryption: "encrypted", reason: null, updated: false })
      );
    };

    // The badge is visible until the content request fails, so a test that expects it to stay waits for the failure first.
    const contentRequestSettled = async () => {
      await vi.waitFor(() => expect(getArtifactFileFromApi).toHaveBeenCalled());
      await new Promise((resolve) => setTimeout(resolve, 100));
    };

    test("shows no badge when the content failed its integrity check", async () => {
      // GIVEN
      confirmedEncrypted();
      vi.mocked(getArtifactFileFromApi).mockResolvedValue(
        contentRequest(
          409,
          "The stored content storage-1 failed its integrity check and was not served."
        )
      );

      // WHEN
      const component = await render(<ArtifactEncryptionBadge artifact={artifact("encrypted")} />);

      // THEN
      await expect
        .element(component.getByTestId("artifact-encryption-badge"))
        .not.toBeInTheDocument();
    });

    test("shows no badge when the file is missing from the storage", async () => {
      // GIVEN
      confirmedEncrypted();
      vi.mocked(getArtifactFileFromApi).mockResolvedValue(
        contentRequest(404, "Unable to find the node storage-1 / StorageObject in the database.")
      );

      // WHEN
      const component = await render(<ArtifactEncryptionBadge artifact={artifact("encrypted")} />);

      // THEN
      await expect
        .element(component.getByTestId("artifact-encryption-badge"))
        .not.toBeInTheDocument();
    });

    test.each([
      [500, "The storage encryption key is not usable. Set INFRAHUB_STORAGE_ENCRYPTION_KEY."],
      [503, "The storage is not available."],
    ])("keeps the badge when the server answered %i", async (status, message) => {
      // GIVEN
      confirmedEncrypted();
      vi.mocked(getArtifactFileFromApi).mockResolvedValue(contentRequest(status, message));

      // WHEN
      const component = await render(<ArtifactEncryptionBadge artifact={artifact("encrypted")} />);

      // THEN
      await contentRequestSettled();
      await expect.element(component.getByTestId("artifact-encryption-badge")).toBeVisible();
    });

    test("keeps the badge when the request fails without an answer", async () => {
      // GIVEN
      confirmedEncrypted();
      vi.mocked(getArtifactFileFromApi).mockRejectedValue(new TypeError("Failed to fetch"));

      // WHEN
      const component = await render(<ArtifactEncryptionBadge artifact={artifact("encrypted")} />);

      // THEN
      await contentRequestSettled();
      await expect.element(component.getByTestId("artifact-encryption-badge")).toBeVisible();
    });

    test("shows the badge only once the content has loaded", async () => {
      // GIVEN
      confirmedEncrypted();
      let resolveContent: (value: Awaited<ReturnType<typeof getArtifactFileFromApi>>) => void =
        () => {};
      vi.mocked(getArtifactFileFromApi).mockReturnValue(
        new Promise((resolve) => {
          resolveContent = resolve;
        })
      );

      // WHEN
      const component = await render(<ArtifactEncryptionBadge artifact={artifact("encrypted")} />);
      await vi.waitFor(() => expect(getArtifactFileFromApi).toHaveBeenCalled());
      await new Promise((resolve) => setTimeout(resolve, 100));

      // THEN
      await expect
        .element(component.getByTestId("artifact-encryption-badge"))
        .not.toBeInTheDocument();

      resolveContent({ data: "content", response: { status: 200 } } as unknown as Awaited<
        ReturnType<typeof getArtifactFileFromApi>
      >);
      await expect.element(component.getByTestId("artifact-encryption-badge")).toBeVisible();
    });

    test("does not request the content of an artifact that has no stored file", async () => {
      // GIVEN
      confirmedEncrypted();
      const withoutFile = {
        ...artifact("encrypted"),
        storage_id: { value: null },
      } as unknown as ArtifactObject;

      // WHEN
      const component = await render(<ArtifactEncryptionBadge artifact={withoutFile} />);

      // THEN
      await expect.element(component.getByTestId("artifact-encryption-badge")).toBeVisible();
      expect(getArtifactFileFromApi).not.toHaveBeenCalled();
    });
  });
});
