import { describe, expect, test, vi } from "vitest";
import { userEvent } from "vitest/browser";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { useUpdateBranchMutation } from "@/entities/branches/ui/queries/update-branch.mutation";

import { render } from "../../../../tests/components/render";
import { BranchEditDescription } from "./branch-edit-description";

vi.mock("@/entities/authentication/ui/useAuth");
vi.mock("@/entities/branches/ui/queries/update-branch.mutation");

const useAuthMock = vi.mocked(useAuth);
const useUpdateBranchMutationMock = vi.mocked(useUpdateBranchMutation);

function mockAuth({ isAuthenticated = true }: { isAuthenticated?: boolean } = {}) {
  useAuthMock.mockReturnValue({
    accessToken: isAuthenticated ? "tok" : null,
    isAuthenticated,
    setToken: vi.fn(),
    user: null,
    data: undefined,
  });
}

function mockMutation({
  mutateAsync = vi.fn().mockResolvedValue(true),
  isPending = false,
}: {
  mutateAsync?: ReturnType<typeof vi.fn>;
  isPending?: boolean;
} = {}) {
  useUpdateBranchMutationMock.mockReturnValue({
    mutateAsync,
    isPending,
  } as unknown as ReturnType<typeof useUpdateBranchMutation>);
  return mutateAsync;
}

describe("BranchEditDescription", () => {
  test("renders the description in view mode", async () => {
    mockAuth();
    mockMutation();

    const component = await render(
      <BranchEditDescription branchName="feature-1" currentDescription="my description" />
    );

    await expect.element(component.getByText("my description")).toBeVisible();
  });

  test("shows placeholder when description is null", async () => {
    mockAuth();
    mockMutation();

    const component = await render(
      <BranchEditDescription branchName="feature-1" currentDescription={null} />
    );

    await expect.element(component.getByText("—")).toBeVisible();
  });

  test("shows pencil when canEdit and authenticated", async () => {
    mockAuth();
    mockMutation();

    const component = await render(
      <BranchEditDescription branchName="feature-1" currentDescription="x" canEdit />
    );

    await expect.element(component.getByTestId("edit-branch-description")).toBeVisible();
  });

  test("hides pencil when canEdit is false", async () => {
    mockAuth();
    mockMutation();

    const component = await render(
      <BranchEditDescription branchName="feature-1" currentDescription="x" canEdit={false} />
    );

    expect(component.getByTestId("edit-branch-description").query()).toBeNull();
  });

  test("hides pencil when not authenticated even if canEdit", async () => {
    mockAuth({ isAuthenticated: false });
    mockMutation();

    const component = await render(
      <BranchEditDescription branchName="feature-1" currentDescription="x" canEdit />
    );

    expect(component.getByTestId("edit-branch-description").query()).toBeNull();
  });

  test("clicking the pencil enters edit mode", async () => {
    mockAuth();
    mockMutation();

    const component = await render(
      <BranchEditDescription branchName="feature-1" currentDescription="x" />
    );
    await component.getByTestId("edit-branch-description").click();

    await expect.element(component.getByTestId("branch-description-input")).toBeVisible();
    await expect.element(component.getByTestId("save-branch-description")).toBeVisible();
    await expect.element(component.getByTestId("cancel-branch-description")).toBeVisible();
  });

  test("save calls the mutation with the typed value", async () => {
    mockAuth();
    const mutate = mockMutation();

    const component = await render(
      <BranchEditDescription branchName="feature-1" currentDescription="old" />
    );
    await component.getByTestId("edit-branch-description").click();
    const input = component.getByTestId("branch-description-input");
    await input.fill("new desc");
    await component.getByTestId("save-branch-description").click();

    expect(mutate).toHaveBeenCalledWith({ name: "feature-1", description: "new desc" });
  });

  test("save success exits edit mode", async () => {
    mockAuth();
    mockMutation();

    const component = await render(
      <BranchEditDescription branchName="feature-1" currentDescription="old" />
    );
    await component.getByTestId("edit-branch-description").click();
    await component.getByTestId("branch-description-input").fill("new desc");
    await component.getByTestId("save-branch-description").click();

    expect(component.getByTestId("branch-description-input").query()).toBeNull();
  });

  test("save failure shows the error message", async () => {
    mockAuth();
    mockMutation({ mutateAsync: vi.fn().mockResolvedValue(false) });

    const component = await render(
      <BranchEditDescription branchName="feature-1" currentDescription="old" />
    );
    await component.getByTestId("edit-branch-description").click();
    await component.getByTestId("save-branch-description").click();

    await expect.element(component.getByText("Update failed")).toBeVisible();
  });

  test("thrown error surfaces the message", async () => {
    mockAuth();
    mockMutation({
      mutateAsync: vi.fn().mockRejectedValue(new Error("Server is on fire")),
    });

    const component = await render(
      <BranchEditDescription branchName="feature-1" currentDescription="old" />
    );
    await component.getByTestId("edit-branch-description").click();
    await component.getByTestId("save-branch-description").click();

    await expect.element(component.getByText("Server is on fire")).toBeVisible();
  });

  test("Enter key triggers save", async () => {
    mockAuth();
    const mutate = mockMutation();

    const component = await render(
      <BranchEditDescription branchName="feature-1" currentDescription="old" />
    );
    await component.getByTestId("edit-branch-description").click();
    const input = component.getByTestId("branch-description-input");
    await input.fill("via enter");
    await userEvent.keyboard("{Enter}");

    expect(mutate).toHaveBeenCalledWith({ name: "feature-1", description: "via enter" });
  });

  test("Escape key cancels edit mode", async () => {
    mockAuth();
    const mutate = mockMutation();

    const component = await render(
      <BranchEditDescription branchName="feature-1" currentDescription="old" />
    );
    await component.getByTestId("edit-branch-description").click();
    await component.getByTestId("branch-description-input").fill("abandon");
    await userEvent.keyboard("{Escape}");

    expect(mutate).not.toHaveBeenCalled();
    expect(component.getByTestId("branch-description-input").query()).toBeNull();
  });

  test("Cancel button reverts to view mode without saving", async () => {
    mockAuth();
    const mutate = mockMutation();

    const component = await render(
      <BranchEditDescription branchName="feature-1" currentDescription="old" />
    );
    await component.getByTestId("edit-branch-description").click();
    await component.getByTestId("branch-description-input").fill("abandon");
    await component.getByTestId("cancel-branch-description").click();

    expect(mutate).not.toHaveBeenCalled();
    expect(component.getByTestId("branch-description-input").query()).toBeNull();
    await expect.element(component.getByText("old")).toBeVisible();
  });

  test("error clears when the input changes", async () => {
    mockAuth();
    mockMutation({ mutateAsync: vi.fn().mockResolvedValue(false) });

    const component = await render(
      <BranchEditDescription branchName="feature-1" currentDescription="old" />
    );
    await component.getByTestId("edit-branch-description").click();
    await component.getByTestId("save-branch-description").click();
    await expect.element(component.getByText("Update failed")).toBeVisible();

    await component.getByTestId("branch-description-input").fill("retry");
    expect(component.getByText("Update failed").query()).toBeNull();
  });

  test("maxLength is enforced on the input", async () => {
    mockAuth();
    mockMutation();

    const component = await render(
      <BranchEditDescription branchName="feature-1" currentDescription="x" />
    );
    await component.getByTestId("edit-branch-description").click();

    await expect
      .element(component.getByTestId("branch-description-input"))
      .toHaveAttribute("maxLength", "1000");
  });
});
