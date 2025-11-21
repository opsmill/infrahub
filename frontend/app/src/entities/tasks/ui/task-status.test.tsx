import { NetworkStatus } from "@apollo/client";
import { describe, expect, test } from "vitest";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getBranchTaskStatusFromApi } from "@/entities/tasks/api/get-branch-task-status-from-api";

import { render } from "../../../../tests/components/render";
import { generateBranch } from "../../../../tests/fake/branch";
import { TaskStatus } from "./task-status";

vi.mock("@/entities/branches/ui/branches-provider");
vi.mock("@/entities/tasks/api/get-branch-task-status-from-api");

describe("TaskStatus", () => {
  const useCurrentBranchMock = vi.mocked(useCurrentBranch);
  const getBranchTaskStatusFromApiMock = vi.mocked(getBranchTaskStatusFromApi);

  test("renders task status with pulse when tasks are running", async () => {
    // GIVEN
    const branch = generateBranch({ name: "branch1" });
    useCurrentBranchMock.mockReturnValue({ currentBranch: branch, setCurrentBranch: () => {} });
    getBranchTaskStatusFromApiMock.mockResolvedValue({
      data: { InfrahubTaskBranchStatus: { count: 1 } },
      loading: false,
      networkStatus: NetworkStatus.ready,
    });

    // WHEN
    const component = await render(<TaskStatus />);

    // THEN
    const taskButton = component.getByRole("link");
    await expect.element(taskButton).toBeVisible();
    await expect
      .element(taskButton)
      .toHaveAttribute("href", expect.stringContaining(encodeURIComponent("branch__value")));
    await expect
      .element(taskButton)
      .toHaveAttribute("href", expect.stringContaining(encodeURIComponent(branch.name)));
    await expect.element(component.getByTestId("pulse")).toBeVisible();
    await taskButton.hover();
    await expect
      .element(component.getByRole("tooltip", { name: "Tasks running on this branch" }))
      .toBeVisible();
  });

  test("renders task status without pulse when no tasks are running", async () => {
    // GIVEN
    useCurrentBranchMock.mockReturnValue({
      currentBranch: generateBranch({ name: "branch1" }),
      setCurrentBranch: () => {},
    });
    getBranchTaskStatusFromApiMock.mockResolvedValue({
      data: { InfrahubTaskBranchStatus: { count: 0 } },
      loading: false,
      networkStatus: NetworkStatus.ready,
    });

    // WHEN
    const component = await render(<TaskStatus />);

    // THEN
    const taskButton = component.getByRole("link", { name: "View branch tasks" });
    await expect.element(taskButton).toBeVisible();
    await taskButton.hover();
    await expect
      .element(component.getByRole("tooltip", { name: "View branch tasks" }))
      .toBeVisible();
    expect(component.getByTestId("pulse").query()).toBeNull();
  });

  test("renders error icon with tooltip when query fails", async () => {
    // GIVEN
    useCurrentBranchMock.mockReturnValue({
      currentBranch: generateBranch({ name: "branch1" }),
      setCurrentBranch: () => {},
    });
    getBranchTaskStatusFromApiMock.mockResolvedValue({
      data: null!,
      error: {} as any,
      loading: false,
      networkStatus: NetworkStatus.error,
    });

    // WHEN
    const component = await render(<TaskStatus />);

    // THEN
    await expect
      .element(component.getByRole("link", { name: "Error checking task status" }))
      .toBeVisible();
  });
});
