import { beforeEach, describe, expect, test, vi } from "vitest";

import { useCheckConnectivityMutation } from "@/entities/repository/domain/check-connectivity.mutation";

import { render } from "../../../../tests/components/render";
import { CheckConnectivityModal } from "./check-connectivity-modal";

vi.mock("@/entities/repository/domain/check-connectivity.mutation");

describe("CheckConnectivityModal", () => {
  const mockMutate = vi.fn();
  const mockOnOpenChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("renders initial state with title and description", async () => {
    // GIVEN
    vi.mocked(useCheckConnectivityMutation).mockReturnValue({
      mutate: mockMutate,
      isPending: false,
      data: undefined,
      error: null,
      isSuccess: false,
    } as unknown as ReturnType<typeof useCheckConnectivityMutation>);

    const component = await render(
      <CheckConnectivityModal repositoryId="repo-1" isOpen onOpenChange={mockOnOpenChange} />
    );

    // THEN
    await expect.element(component.getByRole("dialog")).toBeVisible();
    await expect
      .element(component.getByRole("heading", { name: "Check repository connectivity" }))
      .toBeVisible();
    await expect
      .element(
        component.getByText(
          "Check the connectivity to this repository to validate your connection and authentication status."
        )
      )
      .toBeVisible();
    await expect.element(component.getByRole("button", { name: "Cancel" })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Check now" })).toBeVisible();
  });

  test("calls mutation when clicking Check now button", async () => {
    // GIVEN
    vi.mocked(useCheckConnectivityMutation).mockReturnValue({
      mutate: mockMutate,
      isPending: false,
      data: undefined,
      error: null,
      isSuccess: false,
    } as unknown as ReturnType<typeof useCheckConnectivityMutation>);

    const component = await render(
      <CheckConnectivityModal repositoryId="repo-1" isOpen onOpenChange={mockOnOpenChange} />
    );

    // WHEN
    await component.getByRole("button", { name: "Check now" }).click();

    // THEN
    expect(mockMutate).toHaveBeenCalledWith({ repositoryId: "repo-1" });
  });

  test("shows loading state with updated title when pending", async () => {
    // GIVEN
    vi.mocked(useCheckConnectivityMutation).mockReturnValue({
      mutate: mockMutate,
      isPending: true,
      data: undefined,
      error: null,
      isSuccess: false,
    } as unknown as ReturnType<typeof useCheckConnectivityMutation>);

    const component = await render(
      <CheckConnectivityModal repositoryId="repo-1" isOpen onOpenChange={mockOnOpenChange} />
    );

    // THEN
    await expect
      .element(component.getByRole("heading", { name: "Checking repository connectivity" }))
      .toBeVisible();
    await expect.element(component.getByRole("button", { name: "Check now" })).toBeDisabled();
  });

  test("shows success state when connectivity check succeeds", async () => {
    // GIVEN
    vi.mocked(useCheckConnectivityMutation).mockReturnValue({
      mutate: mockMutate,
      isPending: false,
      data: { ok: true, message: "Connection established successfully" },
      error: null,
      isSuccess: true,
    } as unknown as ReturnType<typeof useCheckConnectivityMutation>);

    const component = await render(
      <CheckConnectivityModal repositoryId="repo-1" isOpen onOpenChange={mockOnOpenChange} />
    );

    // THEN
    await expect
      .element(component.getByRole("heading", { name: "Connection Successful" }))
      .toBeVisible();
    await expect.element(component.getByText("Connection established successfully")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Done" })).toBeVisible();
  });

  test("shows failure state when connectivity check fails with ok=false", async () => {
    // GIVEN
    vi.mocked(useCheckConnectivityMutation).mockReturnValue({
      mutate: mockMutate,
      isPending: false,
      data: { ok: false, message: "Authentication failed" },
      error: null,
      isSuccess: true,
    } as unknown as ReturnType<typeof useCheckConnectivityMutation>);

    const component = await render(
      <CheckConnectivityModal repositoryId="repo-1" isOpen onOpenChange={mockOnOpenChange} />
    );

    // THEN
    await expect
      .element(component.getByRole("heading", { name: "Connection Failed" }))
      .toBeVisible();
    await expect.element(component.getByText("Authentication failed")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Cancel" })).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Retry" })).toBeVisible();
  });

  test("shows failure state when mutation throws an error", async () => {
    // GIVEN
    vi.mocked(useCheckConnectivityMutation).mockReturnValue({
      mutate: mockMutate,
      isPending: false,
      data: undefined,
      error: new Error("Network error"),
      isSuccess: false,
    } as unknown as ReturnType<typeof useCheckConnectivityMutation>);

    const component = await render(
      <CheckConnectivityModal repositoryId="repo-1" isOpen onOpenChange={mockOnOpenChange} />
    );

    // THEN
    await expect
      .element(component.getByRole("heading", { name: "Connection Failed" }))
      .toBeVisible();
    await expect.element(component.getByText("Network error")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Retry" })).toBeVisible();
  });

  test("calls onOpenChange with false when clicking Cancel", async () => {
    // GIVEN
    vi.mocked(useCheckConnectivityMutation).mockReturnValue({
      mutate: mockMutate,
      isPending: false,
      data: undefined,
      error: null,
      isSuccess: false,
    } as unknown as ReturnType<typeof useCheckConnectivityMutation>);

    const component = await render(
      <CheckConnectivityModal repositoryId="repo-1" isOpen onOpenChange={mockOnOpenChange} />
    );

    // WHEN
    await component.getByRole("button", { name: "Cancel" }).click();

    // THEN
    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
  });

  test("calls onOpenChange with false when clicking Done on success", async () => {
    // GIVEN
    vi.mocked(useCheckConnectivityMutation).mockReturnValue({
      mutate: mockMutate,
      isPending: false,
      data: { ok: true, message: "Success" },
      error: null,
      isSuccess: true,
    } as unknown as ReturnType<typeof useCheckConnectivityMutation>);

    const component = await render(
      <CheckConnectivityModal repositoryId="repo-1" isOpen onOpenChange={mockOnOpenChange} />
    );

    // WHEN
    await component.getByRole("button", { name: "Done" }).click();

    // THEN
    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
  });

  test("calls mutation again when clicking Retry on failure", async () => {
    // GIVEN
    vi.mocked(useCheckConnectivityMutation).mockReturnValue({
      mutate: mockMutate,
      isPending: false,
      data: { ok: false, message: "Failed" },
      error: null,
      isSuccess: true,
    } as unknown as ReturnType<typeof useCheckConnectivityMutation>);

    const component = await render(
      <CheckConnectivityModal repositoryId="repo-1" isOpen onOpenChange={mockOnOpenChange} />
    );

    // WHEN
    await component.getByRole("button", { name: "Retry" }).click();

    // THEN
    expect(mockMutate).toHaveBeenCalledWith({ repositoryId: "repo-1" });
  });
});
