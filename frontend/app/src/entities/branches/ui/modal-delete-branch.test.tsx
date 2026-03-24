import { describe, expect, test, vi } from "vitest";
import { userEvent } from "vitest/browser";

import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";

import { render } from "../../../../tests/components/render";
import { DELETE_BRANCH_SCOPE, ModalDeleteBranch } from "./modal-delete-branch";

vi.mock("@/entities/nodes/object/ui/queries/get-objects-count.query");

describe("ModalDeleteBranch", () => {
  const useObjectsCountMock = vi.mocked(useObjectsCount);
  const defaultProps = {
    isOpen: true,
    onOpenChange: vi.fn(),
    onDelete: vi.fn(),
    isLoading: false,
  };

  test("shows scope choice when branch has sync_with_git and repositories exist", async () => {
    // GIVEN
    useObjectsCountMock.mockReturnValue({ data: 1, isLoading: false } as any);
    const branches = [{ name: "feature-1", sync_with_git: true }];

    // WHEN
    const component = await render(
      <ModalDeleteBranch {...defaultProps} branches={branches} />
    );

    // THEN
    await expect
      .element(component.getByRole("radiogroup", { name: "Deletion scope" }))
      .toBeVisible();
  });

  test("does not show scope choice when branch has no sync_with_git", async () => {
    // GIVEN
    useObjectsCountMock.mockReturnValue({ data: 0, isLoading: false } as any);
    const branches = [{ name: "feature-1", sync_with_git: false }];

    // WHEN
    const component = await render(
      <ModalDeleteBranch {...defaultProps} branches={branches} />
    );

    // THEN
    expect(
      component.getByRole("radiogroup", { name: "Deletion scope" }).query()
    ).toBeNull();
  });

  test("defaults to LOCAL scope when modal opens", async () => {
    // GIVEN
    useObjectsCountMock.mockReturnValue({ data: 1, isLoading: false } as any);
    const branches = [{ name: "feature-1", sync_with_git: true }];

    // WHEN
    const component = await render(
      <ModalDeleteBranch {...defaultProps} branches={branches} />
    );

    // THEN
    const localRadio = component.getByRole("radio", { name: /Local only/i });
    await expect.element(localRadio).toBeChecked();
  });

  test("calls onDelete with LOCAL scope when clicking Delete with default selection", async () => {
    // GIVEN
    useObjectsCountMock.mockReturnValue({ data: 1, isLoading: false } as any);
    const onDelete = vi.fn();
    const branches = [{ name: "feature-1", sync_with_git: true }];

    // WHEN
    const component = await render(
      <ModalDeleteBranch {...defaultProps} branches={branches} onDelete={onDelete} />
    );
    await component.getByTestId("modal-delete-confirm").click();

    // THEN
    expect(onDelete).toHaveBeenCalledWith(DELETE_BRANCH_SCOPE.LOCAL);
  });

  test("calls onDelete with LOCAL_AND_REMOTE scope after selecting that option", async () => {
    // GIVEN
    useObjectsCountMock.mockReturnValue({ data: 1, isLoading: false } as any);
    const onDelete = vi.fn();
    const branches = [{ name: "feature-1", sync_with_git: true }];

    // WHEN
    const component = await render(
      <ModalDeleteBranch {...defaultProps} branches={branches} onDelete={onDelete} />
    );
    const remoteRadio = component.getByRole("radio", { name: /Local and remote/i });
    await remoteRadio.click();
    await component.getByTestId("modal-delete-confirm").click();

    // THEN
    expect(onDelete).toHaveBeenCalledWith(DELETE_BRANCH_SCOPE.LOCAL_AND_REMOTE);
  });

  test("calls onDelete with LOCAL scope directly when showScopeChoice is false", async () => {
    // GIVEN
    useObjectsCountMock.mockReturnValue({ data: 0, isLoading: false } as any);
    const onDelete = vi.fn();
    const branches = [{ name: "feature-1", sync_with_git: false }];

    // WHEN
    const component = await render(
      <ModalDeleteBranch {...defaultProps} branches={branches} onDelete={onDelete} />
    );
    await component.getByTestId("modal-delete-confirm").click();

    // THEN
    expect(onDelete).toHaveBeenCalledWith(DELETE_BRANCH_SCOPE.LOCAL);
  });
});
