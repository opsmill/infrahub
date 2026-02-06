import { afterEach, describe, expect, it, vi } from "vitest";

import { queryClient } from "@/shared/api/rest/client";

import { render } from "../../../../../../tests/components/render";
import { RefreshButton } from "./refresh-button";

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>();
  return {
    ...actual,
    useIsFetching: vi.fn(() => 0),
  };
});

import { useIsFetching } from "@tanstack/react-query";

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

  it("invalidates queries when clicking refresh", async () => {
    // GIVEN
    vi.mocked(useIsFetching).mockReturnValue(0);

    const invalidateQueriesSpy = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue(undefined);

    const component = await render(<RefreshButton />);

    // WHEN
    await component.getByRole("button").click();

    // THEN
    expect(invalidateQueriesSpy).toHaveBeenCalledOnce();
  });
});
