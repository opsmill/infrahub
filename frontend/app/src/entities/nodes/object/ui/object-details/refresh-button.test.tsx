import type { Query } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import { queryClient } from "@/shared/api/rest/client";

import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";

import { render } from "../../../../../../tests/components/render";
import { RefreshButton } from "./refresh-button";

describe("RefreshButton", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    queryClient.clear();
  });

  it("disables the button and shows a spinning icon while its refresh runs", async () => {
    // GIVEN
    let finishRefresh = () => {};
    vi.spyOn(queryClient, "invalidateQueries").mockReturnValue(
      new Promise((resolve) => {
        finishRefresh = resolve;
      })
    );
    const component = await render(<RefreshButton />);
    const button = component.getByRole("button");

    // WHEN
    await button.click();

    // THEN
    await expect.element(button).toBeDisabled();
    expect(button.element().querySelector("svg")?.classList.contains("animate-spin")).toBe(true);

    // WHEN
    finishRefresh();

    // THEN
    await expect.element(button).toBeEnabled();
  });

  it("stays idle while a query under its keys fetches in the background", async () => {
    // GIVEN
    queryClient.prefetchQuery({
      queryKey: ["repository", "branch-health", { branchName: "feature" }],
      queryFn: () => new Promise(() => {}),
    });

    // WHEN
    const component = await render(<RefreshButton queryKeys={[["repository"]]} />);

    // THEN
    expect(queryClient.isFetching({ queryKey: ["repository"] })).toBe(1);
    const button = component.getByRole("button");
    await expect.element(button).toBeEnabled();
    expect(button.element().querySelector("svg")?.classList.contains("animate-spin")).toBe(false);
  });

  it("invalidates queries scoped to the default query key when clicking refresh", async () => {
    // GIVEN
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

  it("reads the last update time from the given keys' queries only", async () => {
    // GIVEN
    const findAll = vi.spyOn(queryClient.getQueryCache(), "findAll");

    // WHEN
    await render(<RefreshButton queryKeys={[["repository"], ["tasks"]]} />);

    // THEN
    const filters = findAll.mock.lastCall?.[0];
    expect(filters?.type).toBe("active");
    const isRead = (queryKey: readonly unknown[]) => filters?.predicate?.({ queryKey } as Query);
    expect(isRead(["repository", "branch-repositories", { branchName: "feature" }])).toBe(true);
    expect(isRead(["tasks", "branch-list", "feature"])).toBe(true);
    expect(isRead(["objects", "CoreRepository"])).toBe(false);
  });
});
