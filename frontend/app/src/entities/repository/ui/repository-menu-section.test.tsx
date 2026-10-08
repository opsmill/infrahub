import { Menu } from "@infrahub/ui";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { DeliveryState } from "@/entities/repository/domain/model/delivery-state";
import { retryDelivery } from "@/entities/repository/domain/use-cases/retry-delivery";
import { useGetDeliveryState } from "@/entities/repository/ui/queries/get-delivery-state.query";
import { useImportCurrentCommitMutation } from "@/entities/repository/ui/queries/import-current-commit.mutation";
import { useReimportLastCommitMutation } from "@/entities/repository/ui/queries/reimport-last-commit.mutation";

import { render } from "../../../../tests/components/render";
import { generateBranch } from "../../../../tests/fake/branch";
import { generatePermission } from "../../../../tests/fake/permission";
import { generateNodeSchema } from "../../../../tests/fake/schema";
import { RepositoryMenuSection } from "./repository-menu-section";

vi.mock("@/entities/repository/ui/queries/reimport-last-commit.mutation");
vi.mock("@/entities/repository/ui/queries/import-current-commit.mutation");
vi.mock("@/entities/repository/ui/queries/get-delivery-state.query");
vi.mock("@/entities/repository/domain/use-cases/retry-delivery");
vi.mock("@/entities/branches/ui/queries/get-branches.query");

const refusedPush: DeliveryState = {
  status: "action-required",
  statusLabel: "Action required",
  statusColor: null,
  cause: "permission",
  causeLabel: "Push refused by the remote",
  error: null,
  pendingMerges: [],
  queueVersion: 0,
  lastAbandonment: null,
};

const nothingPending: DeliveryState = {
  status: "none",
  statusLabel: "none",
  statusColor: null,
  cause: null,
  causeLabel: null,
  error: null,
  pendingMerges: [],
  queueVersion: 0,
  lastAbandonment: null,
};

const mockDeliveryState = (state: DeliveryState | undefined) => {
  vi.mocked(useGetDeliveryState).mockReturnValue({
    data: state,
    isPending: state === undefined,
  } as unknown as ReturnType<typeof useGetDeliveryState>);
};

describe("RepositoryMenuSection", () => {
  const mockReimportLastCommit = vi.fn();
  const mockImportCurrentCommit = vi.fn();
  const mockOnCheckConnectivity = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(useReimportLastCommitMutation).mockReturnValue({
      mutate: mockReimportLastCommit,
      isPending: false,
    } as unknown as ReturnType<typeof useReimportLastCommitMutation>);

    vi.mocked(useImportCurrentCommitMutation).mockReturnValue({
      mutate: mockImportCurrentCommit,
      isPending: false,
    } as unknown as ReturnType<typeof useImportCurrentCommitMutation>);

    // The selected branch, "test-branch", is not the default branch.
    vi.mocked(useGetBranches).mockReturnValue({
      data: [
        generateBranch({ name: "test-branch" }),
        generateBranch({ name: "primary", is_default: true }),
      ],
    } as unknown as ReturnType<typeof useGetBranches>);

    mockDeliveryState(refusedPush);
    vi.mocked(retryDelivery).mockResolvedValue({ ok: true, taskId: "task-1" });
  });

  const renderRepositoryMenu = ({
    kind = "CoreRepository",
    permission = generatePermission(),
  }: {
    kind?: string;
    permission?: Permission;
  } = {}) =>
    render(
      <Menu aria-label="Repository actions">
        <RepositoryMenuSection
          repositoryId="repo-1"
          objectSchema={generateNodeSchema({ kind })}
          onCheckConnectivity={mockOnCheckConnectivity}
          permission={permission}
        />
      </Menu>
    );

  test("renders Check connectivity for regular repositories", async () => {
    // GIVEN
    const component = await render(
      <Menu aria-label="Repository actions">
        <RepositoryMenuSection
          repositoryId="repo-1"
          objectSchema={generateNodeSchema({ kind: "CoreRepository" })}
          onCheckConnectivity={mockOnCheckConnectivity}
          permission={generatePermission()}
        />
      </Menu>
    );

    // THEN
    await expect.element(component.getByText("Repository")).toBeVisible();
    await expect
      .element(component.getByRole("menuitem", { name: /Check connectivity/i }))
      .toBeVisible();
    await expect.element(component.baseElement).not.toHaveTextContent("Import latest commit");
  });

  test("renders Import latest commit only for read-only repositories", async () => {
    // GIVEN
    const component = await render(
      <Menu aria-label="Repository actions">
        <RepositoryMenuSection
          repositoryId="repo-1"
          objectSchema={generateNodeSchema({ kind: "CoreReadOnlyRepository" })}
          onCheckConnectivity={mockOnCheckConnectivity}
          permission={generatePermission()}
        />
      </Menu>
    );

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: /Import latest commit/i }))
      .toBeVisible();
  });

  test("calls onCheckConnectivity when clicking Check connectivity", async () => {
    // GIVEN
    const component = await render(
      <Menu aria-label="Repository actions">
        <RepositoryMenuSection
          repositoryId="repo-1"
          objectSchema={generateNodeSchema({ kind: "CoreRepository" })}
          onCheckConnectivity={mockOnCheckConnectivity}
          permission={generatePermission()}
        />
      </Menu>
    );

    // WHEN
    await component.getByRole("menuitem", { name: /Check connectivity/i }).click();

    // THEN
    expect(mockOnCheckConnectivity).toHaveBeenCalled();
  });

  test("calls reimportLastCommit mutation when clicking Import latest commit", async () => {
    // GIVEN
    const component = await render(
      <Menu aria-label="Repository actions">
        <RepositoryMenuSection
          repositoryId="repo-1"
          objectSchema={generateNodeSchema({ kind: "CoreReadOnlyRepository" })}
          onCheckConnectivity={mockOnCheckConnectivity}
          permission={generatePermission()}
        />
      </Menu>
    );

    // WHEN
    await component.getByRole("menuitem", { name: /Import latest commit/i }).click();

    // THEN
    expect(mockReimportLastCommit).toHaveBeenCalledWith({ repositoryId: "repo-1" });
  });

  test("disables Import latest commit when update permission is not allowed", async () => {
    // GIVEN
    const component = await render(
      <Menu aria-label="Repository actions">
        <RepositoryMenuSection
          repositoryId="repo-1"
          objectSchema={generateNodeSchema({ kind: "CoreReadOnlyRepository" })}
          onCheckConnectivity={mockOnCheckConnectivity}
          permission={generatePermission({ update: false })}
        />
      </Menu>
    );

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: /Import latest commit/i }))
      .toHaveAttribute("aria-disabled", "true");
  });

  test("does not show Import latest commit for non-read-only repositories", async () => {
    // GIVEN
    const component = await render(
      <Menu aria-label="Repository actions">
        <RepositoryMenuSection
          repositoryId="repo-1"
          objectSchema={generateNodeSchema({ kind: "CoreRepository" })}
          onCheckConnectivity={mockOnCheckConnectivity}
          permission={generatePermission()}
        />
      </Menu>
    );

    // THEN
    await expect.element(component.baseElement).not.toHaveTextContent("Import latest commit");
  });

  test("shows Reimport current commit only for read-only repositories", async () => {
    // GIVEN
    const component = await render(
      <Menu aria-label="Repository actions">
        <RepositoryMenuSection
          repositoryId="repo-1"
          objectSchema={generateNodeSchema({ kind: "CoreReadOnlyRepository" })}
          onCheckConnectivity={mockOnCheckConnectivity}
          permission={generatePermission()}
        />
      </Menu>
    );

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: /Reimport current commit/i }))
      .toBeVisible();
  });

  test("shows Reimport current commit for non-read-only repositories", async () => {
    // GIVEN
    const component = await render(
      <Menu aria-label="Repository actions">
        <RepositoryMenuSection
          repositoryId="repo-1"
          objectSchema={generateNodeSchema({ kind: "CoreRepository" })}
          onCheckConnectivity={mockOnCheckConnectivity}
          permission={generatePermission()}
        />
      </Menu>
    );

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: /Reimport current commit/i }))
      .toBeVisible();
  });

  test("calls importCurrentCommit mutation when clicking Reimport current commit", async () => {
    // GIVEN
    const component = await render(
      <Menu aria-label="Repository actions">
        <RepositoryMenuSection
          repositoryId="repo-1"
          objectSchema={generateNodeSchema({ kind: "CoreReadOnlyRepository" })}
          onCheckConnectivity={mockOnCheckConnectivity}
          permission={generatePermission()}
        />
      </Menu>
    );

    // WHEN
    await component.getByRole("menuitem", { name: /Reimport current commit/i }).click();

    // THEN
    expect(mockImportCurrentCommit).toHaveBeenCalledWith({ repositoryId: "repo-1" });
  });

  test("enables Retry push for a read-write repository with pending pushes", async () => {
    // GIVEN
    mockDeliveryState(refusedPush);

    // WHEN
    const component = await renderRepositoryMenu();

    // THEN
    const retryItem = component.getByRole("menuitem", { name: "Retry push" });
    await expect.element(retryItem).toBeVisible();
    await expect.element(retryItem).not.toHaveAttribute("aria-disabled", "true");
  });

  test("does not show Retry push for a read-only repository", async () => {
    // GIVEN
    mockDeliveryState(refusedPush);

    // WHEN
    const component = await renderRepositoryMenu({ kind: "CoreReadOnlyRepository" });

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: /Check connectivity/i }))
      .toBeVisible();
    await expect.element(component.baseElement).not.toHaveTextContent("Retry push");
  });

  test.each([
    {
      reason: "without update permission",
      state: refusedPush,
      permission: generatePermission({ update: false }),
    },
    { reason: "when nothing is pending", state: nothingPending, permission: generatePermission() },
    { reason: "while the push state loads", state: undefined, permission: generatePermission() },
  ])("disables Retry push $reason", async ({ state, permission }) => {
    // GIVEN
    mockDeliveryState(state);

    // WHEN
    const component = await renderRepositoryMenu({ permission });

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "Retry push" }))
      .toHaveAttribute("aria-disabled", "true");
  });

  test("retries the pending pushes on the default branch while another branch is selected", async () => {
    // GIVEN
    const component = await renderRepositoryMenu();

    // WHEN
    await component.getByRole("menuitem", { name: "Retry push" }).click();

    // THEN
    await vi.waitFor(() =>
      expect(retryDelivery).toHaveBeenCalledWith({ branchName: "primary", repositoryId: "repo-1" })
    );
  });

  test("links to the task when the retry starts", async () => {
    // GIVEN
    const component = await renderRepositoryMenu();

    // WHEN
    await component.getByRole("menuitem", { name: "Retry push" }).click();

    // THEN
    await expect.element(component.getByText("Retry of the pending pushes started.")).toBeVisible();
    await expect
      .element(component.getByRole("link", { name: "View task" }))
      .toHaveAttribute("href", "/tasks/task-1");
  });

  test("shows the refusal message of the backend when the retry is refused", async () => {
    // GIVEN
    vi.mocked(retryDelivery).mockRejectedValue(
      new Error("Repository repo-a has nothing pending to push.")
    );
    const component = await renderRepositoryMenu();

    // WHEN
    await component.getByRole("menuitem", { name: "Retry push" }).click();

    // THEN
    await expect
      .element(
        component.getByText(
          "Error retrying the pending pushes: Repository repo-a has nothing pending to push."
        )
      )
      .toBeVisible();
  });
});
