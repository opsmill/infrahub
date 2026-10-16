import { Menu } from "@infrahub/ui";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";
import {
  EDIT_DEFAULT_BRANCH,
  MANAGE_REPOSITORIES,
  type Permission,
} from "@/entities/permission/domain/model/permission";
import { getObjectPermissions } from "@/entities/permission/domain/use-cases/get-object-permissions";
import { useHasGlobalPermission } from "@/entities/permission/ui/queries/has-global-permission.query";
import type { RepositoryPushState } from "@/entities/repository/domain/model/repository-push-state";
import { retryPush } from "@/entities/repository/domain/use-cases/retry-push";
import { useGetRepositoryPushState } from "@/entities/repository/ui/queries/get-repository-push-state.query";
import { useImportCurrentCommitMutation } from "@/entities/repository/ui/queries/import-current-commit.mutation";
import { useReimportLastCommitMutation } from "@/entities/repository/ui/queries/reimport-last-commit.mutation";

import { render } from "../../../../tests/components/render";
import { initPointerTracking } from "../../../../tests/components/utils";
import { generateBranch } from "../../../../tests/fake/branch";
import { generatePermission } from "../../../../tests/fake/permission";
import { generateNodeSchema } from "../../../../tests/fake/schema";
import { RepositoryMenuSection } from "./repository-menu-section";

vi.mock("@/entities/repository/ui/queries/reimport-last-commit.mutation");
vi.mock("@/entities/repository/ui/queries/import-current-commit.mutation");
vi.mock("@/entities/repository/ui/queries/get-repository-push-state.query");
vi.mock("@/entities/repository/domain/use-cases/retry-push");
vi.mock("@/entities/branches/ui/queries/get-branches.query");
vi.mock("@/entities/permission/ui/queries/has-global-permission.query");
vi.mock("@/entities/permission/domain/use-cases/get-object-permissions");

const refusedPush: RepositoryPushState = {
  status: "action-required",
  statusLabel: "Action required",
  statusColor: null,
  cause: "permission",
  causeLabel: "Push refused by the remote",
  error: null,
  pendingMerges: [],
  queueVersion: 0,
  lastAbandonedPush: null,
};

const nothingPending: RepositoryPushState = {
  status: "none",
  statusLabel: "none",
  statusColor: null,
  cause: null,
  causeLabel: null,
  error: null,
  pendingMerges: [],
  queueVersion: 0,
  lastAbandonedPush: null,
};

const mockPushState = (state: RepositoryPushState | undefined) => {
  vi.mocked(useGetRepositoryPushState).mockReturnValue({
    data: state,
    isPending: state === undefined,
    isError: false,
  } as unknown as ReturnType<typeof useGetRepositoryPushState>);
};

const mockUnreadablePushState = () => {
  vi.mocked(useGetRepositoryPushState).mockReturnValue({
    data: undefined,
    isPending: false,
    isError: true,
  } as unknown as ReturnType<typeof useGetRepositoryPushState>);
};

const ALL_GLOBAL_PERMISSIONS = [MANAGE_REPOSITORIES, EDIT_DEFAULT_BRANCH];

const mockGlobalPermissions = (granted: string[]) => {
  vi.mocked(useHasGlobalPermission).mockImplementation(
    (action) =>
      ({ data: granted.includes(action) }) as unknown as ReturnType<typeof useHasGlobalPermission>
  );
};

describe("RepositoryMenuSection", () => {
  const mockReimportLastCommit = vi.fn();
  const mockImportCurrentCommit = vi.fn();
  const mockOnCheckConnectivity = vi.fn();
  const mockOnAbandonPush = vi.fn();

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

    mockPushState(refusedPush);
    mockGlobalPermissions(ALL_GLOBAL_PERMISSIONS);
    vi.mocked(getObjectPermissions).mockResolvedValue(generatePermission());
    vi.mocked(retryPush).mockResolvedValue({ ok: true, taskId: "task-1" });
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
          onAbandonPush={mockOnAbandonPush}
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
          onAbandonPush={mockOnAbandonPush}
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
          onAbandonPush={mockOnAbandonPush}
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
          onAbandonPush={mockOnAbandonPush}
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
          onAbandonPush={mockOnAbandonPush}
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
          onAbandonPush={mockOnAbandonPush}
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
          onAbandonPush={mockOnAbandonPush}
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
          onAbandonPush={mockOnAbandonPush}
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
          onAbandonPush={mockOnAbandonPush}
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
          onAbandonPush={mockOnAbandonPush}
          permission={generatePermission()}
        />
      </Menu>
    );

    // WHEN
    await component.getByRole("menuitem", { name: /Reimport current commit/i }).click();

    // THEN
    expect(mockImportCurrentCommit).toHaveBeenCalledWith({ repositoryId: "repo-1" });
  });

  test.each(["Retry push", "Abandon pending push"])(
    "enables %s for a read-write repository with pending pushes",
    async (itemName) => {
      // GIVEN
      mockPushState(refusedPush);

      // WHEN
      const component = await renderRepositoryMenu();

      // THEN
      const item = component.getByRole("menuitem", { name: itemName });
      await expect.element(item).toBeVisible();
      await expect.element(item).not.toHaveAttribute("aria-disabled", "true");
    }
  );

  test("does not show the push items for a read-only repository", async () => {
    // GIVEN
    mockPushState(refusedPush);

    // WHEN
    const component = await renderRepositoryMenu({ kind: "CoreReadOnlyRepository" });

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: /Check connectivity/i }))
      .toBeVisible();
    await expect.element(component.baseElement).not.toHaveTextContent("Retry push");
    await expect.element(component.baseElement).not.toHaveTextContent("Abandon pending push");
  });

  test.each(
    ["Retry push", "Abandon pending push"].flatMap((itemName) => [
      {
        itemName,
        reason: "without update permission on the default branch",
        state: refusedPush,
        defaultBranchPermission: generatePermission({ update: false }),
        globalPermissions: ALL_GLOBAL_PERMISSIONS,
      },
      {
        itemName,
        reason: "without the global permission to manage repositories",
        state: refusedPush,
        defaultBranchPermission: generatePermission(),
        globalPermissions: [EDIT_DEFAULT_BRANCH],
      },
      {
        itemName,
        reason: "without the global permission to edit the default branch",
        state: refusedPush,
        defaultBranchPermission: generatePermission(),
        globalPermissions: [MANAGE_REPOSITORIES],
      },
      {
        itemName,
        reason: "when nothing is pending",
        state: nothingPending,
        defaultBranchPermission: generatePermission(),
        globalPermissions: ALL_GLOBAL_PERMISSIONS,
      },
      {
        itemName,
        reason: "while the push state loads",
        state: undefined,
        defaultBranchPermission: generatePermission(),
        globalPermissions: ALL_GLOBAL_PERMISSIONS,
      },
    ])
  )(
    "disables $itemName $reason",
    async ({ itemName, state, defaultBranchPermission, globalPermissions }) => {
      // GIVEN
      mockPushState(state);
      mockGlobalPermissions(globalPermissions);
      vi.mocked(getObjectPermissions).mockResolvedValue(defaultBranchPermission);

      // WHEN
      const component = await renderRepositoryMenu();

      // THEN
      await vi.waitFor(() => expect(getObjectPermissions).toHaveBeenCalled());
      await expect
        .element(component.getByRole("menuitem", { name: itemName }))
        .toHaveAttribute("aria-disabled", "true");
    }
  );

  test.each(["Retry push", "Abandon pending push"])(
    "enables %s from the update permission on the default branch while the selected branch denies it",
    async (itemName) => {
      // GIVEN
      mockPushState(refusedPush);

      // WHEN
      const component = await renderRepositoryMenu({
        permission: generatePermission({ update: false }),
      });

      // THEN
      await expect
        .element(component.getByRole("menuitem", { name: itemName }))
        .not.toHaveAttribute("aria-disabled", "true");
      expect(getObjectPermissions).toHaveBeenCalledWith(
        expect.objectContaining({ kind: "CoreRepository", branchName: "primary" })
      );
    }
  );

  test("keeps Retry push and disables Abandon pending push when the push state cannot be read", async () => {
    // GIVEN
    mockUnreadablePushState();

    // WHEN
    const component = await renderRepositoryMenu();

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "Retry push" }))
      .not.toHaveAttribute("aria-disabled", "true");
    await expect
      .element(component.getByRole("menuitem", { name: "Abandon pending push" }))
      .toHaveAttribute("aria-disabled", "true");
  });

  test("disables Abandon pending push when a reload of the push state fails", async () => {
    // GIVEN
    vi.mocked(useGetRepositoryPushState).mockReturnValue({
      data: refusedPush,
      isPending: false,
      isError: true,
    } as unknown as ReturnType<typeof useGetRepositoryPushState>);

    // WHEN
    const component = await renderRepositoryMenu();

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: "Abandon pending push" }))
      .toHaveAttribute("aria-disabled", "true");
  });

  test.each([
    {
      itemName: "Retry push",
      reason: "without the permission",
      arrange: () => mockGlobalPermissions([EDIT_DEFAULT_BRANCH]),
      tooltip: "Ask an administrator for access",
    },
    {
      itemName: "Abandon pending push",
      reason: "without the permission",
      arrange: () => mockGlobalPermissions([EDIT_DEFAULT_BRANCH]),
      tooltip: "Ask an administrator for access",
    },
    {
      itemName: "Retry push",
      reason: "when nothing is pending",
      arrange: () => mockPushState(nothingPending),
      tooltip: "Nothing to push",
    },
    {
      itemName: "Abandon pending push",
      reason: "when nothing is pending",
      arrange: () => mockPushState(nothingPending),
      tooltip: "Nothing to push",
    },
    {
      itemName: "Abandon pending push",
      reason: "when the push state cannot be read",
      arrange: mockUnreadablePushState,
      tooltip: "Couldn't load the pending pushes. Reload the page",
    },
  ])("explains why $itemName is disabled $reason", async ({ itemName, arrange, tooltip }) => {
    // GIVEN
    arrange();
    const component = await renderRepositoryMenu();
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByRole("menuitem", { name: itemName }).hover();

    // THEN
    await expect.element(component.getByRole("tooltip", { name: tooltip })).toBeVisible();
  });

  test("disables Reimport current commit without update permission", async () => {
    // WHEN
    const component = await renderRepositoryMenu({
      permission: generatePermission({ update: false }),
    });

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: /Reimport current commit/i }))
      .toHaveAttribute("aria-disabled", "true");
  });

  test("retries the pending pushes on the default branch while another branch is selected", async () => {
    // GIVEN
    const component = await renderRepositoryMenu();

    // WHEN
    await component.getByRole("menuitem", { name: "Retry push" }).click();

    // THEN
    await vi.waitFor(() =>
      expect(retryPush).toHaveBeenCalledWith({ branchName: "primary", repositoryId: "repo-1" })
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
    vi.mocked(retryPush).mockRejectedValue(
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

  test("opens the abandon dialog", async () => {
    // GIVEN
    const component = await renderRepositoryMenu();

    // WHEN
    await component.getByRole("menuitem", { name: "Abandon pending push" }).click();

    // THEN
    expect(mockOnAbandonPush).toHaveBeenCalled();
  });
});
