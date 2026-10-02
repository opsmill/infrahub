import { type Query, useIsFetching } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import { queryClient } from "@/shared/api/rest/client";

import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";

import { render } from "../../../../../../tests/components/render";
import { RefreshButton } from "./refresh-button";

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>();
  return {
    ...actual,
    useIsFetching: vi.fn(() => 0),
  };
});

describe("RefreshButton", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("disables the button and shows a spinning icon while refetching", async () => {
    // GIVEN
    vi.mocked(useIsFetching).mockReturnValue(1);

    const component = await render(<RefreshButton />);

    // THEN
    const button = component.getByRole("button");
    await expect.element(button).toBeDisabled();

    const icon = button.element().querySelector("svg");
    expect(icon).not.toBeNull();
    expect(icon?.classList.contains("animate-spin")).toBe(true);
  });

  it("invalidates queries scoped to the default query key when clicking refresh", async () => {
    // GIVEN
    vi.mocked(useIsFetching).mockReturnValue(0);

    const invalidateQueriesSpy = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue(undefined);

    const component = await render(<RefreshButton />);

    // WHEN
    await component.getByRole("button").click();

    // THEN
    expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: objectQueryKeys.all });
  });

  it("invalidates every given query key", async () => {
    // GIVEN
    const firstKey = ["branches", "details", "feature"] as const;
    const secondKey = ["repository"] as const;
    vi.mocked(useIsFetching).mockReturnValue(0);

    const invalidateQueriesSpy = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue(undefined);

    const component = await render(<RefreshButton queryKeys={[firstKey, secondKey]} />);

    // WHEN
    await component.getByRole("button").click();

    // THEN
    expect(invalidateQueriesSpy).toHaveBeenCalledTimes(2);
    expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: firstKey });
    expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: secondKey });
  });

  it("watches queries under any of the given key prefixes", async () => {
    // GIVEN
    vi.mocked(useIsFetching).mockReturnValue(0);

    await render(<RefreshButton queryKeys={[["repository"], ["tasks"]]} />);

    // THEN
    const predicate = vi.mocked(useIsFetching).mock.lastCall?.[0]?.predicate;
    expect(predicate).toBeDefined();
    const isWatched = (queryKey: readonly unknown[]) => predicate?.({ queryKey } as Query);
    expect(isWatched(["repository", "branch-repositories", { branchName: "feature" }])).toBe(true);
    expect(isWatched(["tasks", "branch-list", "feature"])).toBe(true);
    expect(isWatched(["objects", "CoreRepository"])).toBe(false);
  });

  it("reads the last update time from the given keys' queries only", async () => {
    // GIVEN
    vi.mocked(useIsFetching).mockReturnValue(0);
    const findAll = vi.spyOn(queryClient.getQueryCache(), "findAll");

    // WHEN
    await render(<RefreshButton queryKeys={[["tasks"]]} />);

    // THEN
    const filters = findAll.mock.lastCall?.[0];
    expect(filters?.type).toBe("active");
    const isRead = (queryKey: readonly unknown[]) => filters?.predicate?.({ queryKey } as Query);
    expect(isRead(["tasks", "branch-list", "feature"])).toBe(true);
    expect(isRead(["objects", "CoreRepository"])).toBe(false);
  });

  it("is busy only while a query under one of the given keys is fetching", async () => {
    // GIVEN
    const fetchingQueryKey = (queryKey: readonly unknown[]) =>
      vi
        .mocked(useIsFetching)
        .mockImplementation((filters) => (filters?.predicate?.({ queryKey } as Query) ? 1 : 0));

    // WHEN
    fetchingQueryKey(["objects", "CoreRepository"]);
    const idle = await render(<RefreshButton queryKeys={[["repository"], ["tasks"]]} />);

    // THEN
    await expect.element(idle.getByRole("button")).toBeEnabled();
    await idle.unmount();

    // WHEN
    fetchingQueryKey(["tasks", "branch-list", "feature"]);
    const busy = await render(<RefreshButton queryKeys={[["repository"], ["tasks"]]} />);

    // THEN
    await expect.element(busy.getByRole("button")).toBeDisabled();
  });
});
