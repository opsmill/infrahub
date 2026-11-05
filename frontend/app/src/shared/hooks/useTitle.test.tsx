import { afterEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { useTitle } from "@/shared/hooks/useTitle";

import { useConfig } from "@/entities/config/ui/config-provider";

import { generateConfig } from "../../../tests/fake/config";

vi.mock("@/entities/config/ui/config-provider");

const withLabel = (label: string | null) => generateConfig({ instance: { label, color: null } });

describe("useTitle", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  test("prefixes the page title with the instance label", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(withLabel("QA"));

    // WHEN
    await renderHook(() => useTitle("Schema"));

    // THEN
    expect(document.title).toBe("QA · Schema");
  });

  test("uses the page title alone when no instance label is set", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(withLabel(null));

    // WHEN
    await renderHook(() => useTitle("Schema"));

    // THEN
    expect(document.title).toBe("Schema");
  });

  test("updates the title when the instance label changes while mounted", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(withLabel("QA"));
    const { rerender } = await renderHook(() => useTitle("Schema"));
    vi.mocked(useConfig).mockReturnValue(withLabel("Staging"));

    // WHEN
    await rerender();

    // THEN
    expect(document.title).toBe("Staging · Schema");
  });

  test("restores a composed default title on unmount", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(withLabel("QA"));
    const { unmount } = await renderHook(() => useTitle("Schema"));

    // WHEN
    await unmount();

    // THEN
    expect(document.title).toBe("QA · Infrahub");
  });

  test("restores a title carrying the label current at unmount, not the one at mount", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(withLabel("QA"));
    const { rerender, unmount } = await renderHook(() => useTitle("Schema"));
    vi.mocked(useConfig).mockReturnValue(withLabel("Staging"));
    await rerender();

    // WHEN
    await unmount();

    // THEN
    expect(document.title).toBe("Staging · Infrahub");
  });
});
