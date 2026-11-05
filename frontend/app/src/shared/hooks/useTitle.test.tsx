import { useAtomValue } from "jotai";
import { describe, expect, test } from "vitest";
import { renderHook } from "vitest-browser-react";

import { useTitle } from "@/shared/hooks/useTitle";
import { pageTitleAtom } from "@/shared/stores/page-title.atom";

const useTitleWithRegistered = (title: string) => {
  useTitle(title);
  return useAtomValue(pageTitleAtom);
};

describe("useTitle", () => {
  test("registers the page title", async () => {
    // GIVEN
    const title = "Schema";

    // WHEN
    const { result } = await renderHook(() => useTitleWithRegistered(title));

    // THEN
    expect(result.current).toBe("Schema");
  });

  test("replaces the registered title when the page title changes", async () => {
    // GIVEN
    const { result, rerender } = await renderHook(
      (title: string = "Loading") => useTitleWithRegistered(title),
      { initialProps: "Loading" }
    );

    // WHEN
    await rerender("Device details");

    // THEN
    expect(result.current).toBe("Device details");
  });

  test("clears the registered title on unmount", async () => {
    // GIVEN
    const { unmount } = await renderHook(() => useTitle("Schema"));

    // WHEN
    await unmount();

    // THEN
    const { result } = await renderHook(() => useAtomValue(pageTitleAtom));
    expect(result.current).toBeNull();
  });

  test("falls back to the earlier registration when the latest one unmounts", async () => {
    // GIVEN
    const parent = await renderHook(() => useTitleWithRegistered("Profile"));
    const child = await renderHook(() => useTitle("Tokens"));

    // WHEN
    await child.unmount();

    // THEN
    expect(parent.result.current).toBe("Profile");
  });
});
