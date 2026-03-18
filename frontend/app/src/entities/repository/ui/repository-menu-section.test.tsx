import { beforeEach, describe, expect, test, vi } from "vitest";

import { Menu } from "@/shared/components/aria/menu";

import { useImportCurrentCommitMutation } from "@/entities/repository/domain/import-current-commit.mutation";
import { useReimportLastCommitMutation } from "@/entities/repository/domain/reimport-last-commit.mutation";

import { render } from "../../../../tests/components/render";
import { generatePermission } from "../../../../tests/fake/permission";
import { generateNodeSchema } from "../../../../tests/fake/schema";
import { RepositoryMenuSection } from "./repository-menu-section";

vi.mock("@/entities/repository/domain/reimport-last-commit.mutation");
vi.mock("@/entities/repository/domain/import-current-commit.mutation");

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
  });

  test("renders Check connectivity and Import latest commit menu items", async () => {
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
          objectSchema={generateNodeSchema({ kind: "CoreRepository" })}
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
          objectSchema={generateNodeSchema({ kind: "CoreRepository" })}
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

  test("does not show Reimport current commit for non-read-only repositories", async () => {
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
    await expect.element(component.baseElement).not.toHaveTextContent("Reimport current commit");
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
});
