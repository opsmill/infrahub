import { describe, expect, test, vi } from "vitest";

import { retryTaskFromApi } from "@/entities/tasks/api/retry-task-from-api";
import { TaskActions } from "@/entities/tasks/ui/task-actions";

import { render } from "../../../../tests/components/render";

vi.mock("@/entities/tasks/api/retry-task-from-api");
vi.mock("@/entities/tasks/api/cancel-task-from-api");

const retryTaskFromApiMock = vi.mocked(retryTaskFromApi);

describe("TaskActions", () => {
  test("shows the Retry action when it is available and opens a confirmation", async () => {
    const task = {
      id: "task-1",
      title: "Generate artifact startup-config",
      state: "COMPLETED",
      available_actions: [
        { action: "RETRY", available: true, unavailability_reason: null },
        { action: "CANCEL", available: false, unavailability_reason: "Delivery already settled" },
      ],
    };

    const component = await render(<TaskActions task={task} />);

    const retryButton = component.getByRole("button", { name: "Retry" });
    await expect.element(retryButton).toBeVisible();

    await retryButton.click();

    await expect
      .element(component.getByText('Retry "Generate artifact startup-config" task?'))
      .toBeVisible();
    await expect.element(component.getByText(/The current one stays Completed/)).toBeVisible();
  });

  test("shows the Cancel action when it is available and opens a destructive confirmation", async () => {
    const task = {
      id: "task-3",
      title: "Rebase branch ord1-add-upstream",
      state: "SCHEDULED",
      available_actions: [
        { action: "RETRY", available: false, unavailability_reason: "Delivery still in progress" },
        { action: "CANCEL", available: true, unavailability_reason: null },
      ],
    };

    const component = await render(<TaskActions task={task} />);

    const cancelButton = component.getByRole("button", { name: "Cancel" });
    await expect.element(cancelButton).toBeVisible();

    await cancelButton.click();

    await expect
      .element(component.getByText('Cancel "Rebase branch ord1-add-upstream" task?'))
      .toBeVisible();
    await expect.element(component.getByRole("button", { name: "Cancel task" })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Keep task" })).toBeVisible();
  });

  test("renders no action when the task exposes none", async () => {
    const task = {
      id: "task-2",
      title: "Some non-delivery task",
      state: "COMPLETED",
      available_actions: [],
    };

    const component = await render(<TaskActions task={task} />);

    await expect.element(component.getByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    expect(retryTaskFromApiMock).not.toHaveBeenCalled();
  });
});
