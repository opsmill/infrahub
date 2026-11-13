import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createStore, Provider } from "jotai";
import type React from "react";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { checkArtifactEncryption } from "@/entities/artifacts/domain/use-cases/check-artifact-encryption";
import { useCheckArtifactEncryption } from "@/entities/artifacts/ui/queries/check-artifact-encryption.query";
import { BranchContext } from "@/entities/branches/ui/branches-provider";

import { generateBranch } from "../../../../../tests/fake/branch";

vi.mock("@/entities/artifacts/domain/use-cases/check-artifact-encryption");

const wrapperAt = (date: Date | null) => {
  const store = createStore();
  store.set(datetimeAtom, date);

  return ({ children }: { children: React.ReactNode }) => (
    <Provider store={store}>
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <BranchContext value={{ currentBranch: generateBranch(), setCurrentBranch: () => {} }}>
          {children}
        </BranchContext>
      </QueryClientProvider>
    </Provider>
  );
};

describe("useCheckArtifactEncryption", () => {
  const checkArtifactEncryptionMock = vi.mocked(checkArtifactEncryption);

  beforeEach(() => {
    checkArtifactEncryptionMock.mockReset();
    checkArtifactEncryptionMock.mockResolvedValue({ encryption: "encrypted", updated: false });
  });

  test("sends the check when the current data is viewed", async () => {
    // WHEN
    const { result } = await renderHook(() => useCheckArtifactEncryption("artifact-1"), {
      wrapper: wrapperAt(null),
    });

    // THEN
    await expect.poll(() => result.current.data).toMatchObject({ encryption: "encrypted" });
    expect(checkArtifactEncryptionMock).toHaveBeenCalledTimes(1);
  });

  test("does not send the check while a past date is viewed", async () => {
    // WHEN
    const { result } = await renderHook(() => useCheckArtifactEncryption("artifact-1"), {
      wrapper: wrapperAt(new Date("2026-01-01T00:00:00Z")),
    });

    // THEN
    expect(result.current.fetchStatus).toBe("idle");
    expect(result.current.data).toBeUndefined();
    expect(checkArtifactEncryptionMock).not.toHaveBeenCalled();
  });
});
