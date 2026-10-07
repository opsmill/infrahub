import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { page } from "vitest/browser";

import {
  BranchRepositoriesError,
  type BranchRepository,
  type BranchRepositoryHealth,
} from "@/entities/repository/domain/model/branch-repository";
import { getBranchRepositories } from "@/entities/repository/domain/use-cases/get-branch-repositories";
import { getBranchRepositoryHealth } from "@/entities/repository/domain/use-cases/get-branch-repository-health";
import { useGetRepositoryImportError } from "@/entities/repository/ui/queries/get-repository-import-error.query";

import { render } from "../../../../../tests/components/render";
import { initPointerTracking } from "../../../../../tests/components/utils";
import {
  buildBranchRepositoriesScenario,
  generateBranchRepository,
  MANY_ERRORS_IMPORT_ERROR_POSITIONS,
  toBranchRepositoryHealth,
  toBranchRepositoryPage,
} from "../../../../../tests/fake/branch-repositories";
import { BranchRepositoriesCard } from "./branch-repositories-card";

vi.mock("@/entities/repository/domain/use-cases/get-branch-repositories");
vi.mock("@/entities/repository/domain/use-cases/get-branch-repository-health");
vi.mock("@/entities/repository/ui/queries/get-repository-import-error.query");

const serve = (
  repositories: BranchRepository[],
  health: BranchRepositoryHealth = toBranchRepositoryHealth(repositories)
) => {
  vi.mocked(getBranchRepositories).mockImplementation(async ({ offset, limit }) =>
    toBranchRepositoryPage(repositories, { offset, limit })
  );
  vi.mocked(getBranchRepositoryHealth).mockResolvedValue(health);
};

const renderCard = ({
  syncWithGit = true,
  search = "",
}: {
  syncWithGit?: boolean;
  search?: string;
} = {}) => {
  window.history.replaceState(null, "", `/branches/feature?branch=main${search}`);
  return render(<BranchRepositoriesCard branchName="feature" syncWithGit={syncWithGit} />);
};

const bodyRows = (container: HTMLElement) => [...container.querySelectorAll("tbody tr")];

const rowNames = (container: HTMLElement) =>
  bodyRows(container).map((row) => row.querySelector("a")?.textContent);

const requestedOffsets = () =>
  vi.mocked(getBranchRepositories).mock.calls.map(([params]) => params.offset);

describe("BranchRepositoriesCard", () => {
  let initialUrl: string;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useGetRepositoryImportError).mockReturnValue(undefined);
    initialUrl = window.location.href;
  });

  afterEach(() => {
    window.history.replaceState(null, "", initialUrl);
    vi.unstubAllGlobals();
  });

  test("lists every repository with its Git state and commit, and the count in the header", async () => {
    // GIVEN
    serve(buildBranchRepositoriesScenario("all-clear"));

    // WHEN
    const component = await renderCard();

    // THEN
    await expect
      .element(component.getByRole("link", { name: "infrastructure-templates" }))
      .toBeVisible();
    await expect.element(component.getByText("Git repositories")).toBeVisible();
    expect(bodyRows(component.container)).toHaveLength(4);
    await expect.element(component.getByText("4", { exact: true })).toBeVisible();
    await expect.element(component.getByText("In Sync").first()).toBeVisible();
    await expect.element(component.getByText("8f3c2a1")).toHaveAttribute("title", "8f3c2a1");
  });

  test("asks the server for one page of the branch's repositories", async () => {
    // GIVEN
    serve(buildBranchRepositoriesScenario("all-clear"));

    // WHEN
    const component = await renderCard({ syncWithGit: false });

    // THEN
    await expect.element(component.getByText("infrastructure-templates")).toBeVisible();
    expect(getBranchRepositories).toHaveBeenCalledWith({
      branchName: "feature",
      syncWithGit: false,
      limit: 10,
      offset: 0,
    });
    expect(getBranchRepositoryHealth).toHaveBeenCalledWith({
      branchName: "feature",
      syncWithGit: false,
    });
  });

  test("tags read-only repositories", async () => {
    // GIVEN
    serve(buildBranchRepositoriesScenario("all-clear"));

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("vendor-golden-configs")).toBeVisible();
    const readOnlyRow = bodyRows(component.container).find((row) =>
      row.textContent?.includes("vendor-golden-configs")
    );
    expect(readOnlyRow?.textContent).toContain("Read-only");
    expect(component.container.textContent?.match(/Read-only/g)).toHaveLength(1);
  });

  test("keeps the server's order: failing repositories stay where they are, the bands name them", async () => {
    // GIVEN
    const repositories = buildBranchRepositoriesScenario("many-errors");
    serve(repositories);

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText(/more repositories with errors/)).toBeVisible();
    expect(rowNames(component.container)).toEqual(
      repositories.slice(0, 10).map(({ name }) => name)
    );
    const failingCount = MANY_ERRORS_IMPORT_ERROR_POSITIONS.length;
    expect(
      component.container.querySelectorAll('[data-testid="repository-error-band"]')
    ).toHaveLength(3);
    await expect
      .element(
        component.getByText(`${failingCount - 3} more repositories with errors`, { exact: false })
      )
      .toBeVisible();
  });

  test("shows the server's total in the count badge, not the rows on the page", async () => {
    // GIVEN
    serve(buildBranchRepositoriesScenario("many-errors"));

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("40", { exact: true })).toBeVisible();
    expect(bodyRows(component.container)).toHaveLength(10);
  });

  test("keeps the table height on a short last page", async () => {
    // GIVEN
    serve(buildBranchRepositoriesScenario("eleven"));

    // WHEN
    const component = await renderCard({ search: "&repositories_page=2" });

    // THEN
    await expect
      .element(component.getByRole("navigation", { name: "Repositories pagination" }))
      .toBeVisible();
    expect(bodyRows(component.container)).toHaveLength(1);
    await expect
      .element(component.getByTestId("branch-repositories-table"))
      .toHaveStyle({ minHeight: "440px" });
  });

  test("moves to the next page through the pager and puts it in the url", async () => {
    // GIVEN
    serve(buildBranchRepositoriesScenario("eleven"));
    const component = await renderCard();
    await expect.element(component.getByRole("button", { name: "Next page" })).toBeVisible();

    // WHEN
    await component.getByRole("button", { name: "Next page" }).click();

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Page 2" }))
      .toHaveAttribute("aria-current", "page");
    expect(bodyRows(component.container)).toHaveLength(1);
    expect(new URL(window.location.href).searchParams.get("repositories_page")).toBe("2");
    expect(requestedOffsets()).toContain(10);
  });

  test("shows the last page for a page past the end, once the server's count is known", async () => {
    // GIVEN
    serve(buildBranchRepositoriesScenario("eleven"));

    // WHEN
    const component = await renderCard({ search: "&repositories_page=99" });

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Page 2" }))
      .toHaveAttribute("aria-current", "page");
    expect(bodyRows(component.container)).toHaveLength(1);
    expect(requestedOffsets()).toEqual([980, 10]);
  });

  test("shows page 1 for a page below 1", async () => {
    // GIVEN
    serve(buildBranchRepositoriesScenario("eleven"));

    // WHEN
    const component = await renderCard({ search: "&repositories_page=0" });

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Page 1" }))
      .toHaveAttribute("aria-current", "page");
    expect(bodyRows(component.container)).toHaveLength(10);
    expect(requestedOffsets()).toEqual([0]);
  });

  test("shows all 10 rows and no pager for exactly 10 repositories", async () => {
    // GIVEN
    serve(buildBranchRepositoriesScenario("exactly-10"));

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByTestId("branch-repositories-table")).toBeVisible();
    expect(bodyRows(component.container)).toHaveLength(10);
    expect(component.container.querySelector("nav")).toBeNull();
    await expect
      .element(component.getByTestId("branch-repositories-table"))
      .not.toHaveAttribute("style");
  });

  test("shows placeholder rows and no count while loading", async () => {
    // GIVEN
    vi.mocked(getBranchRepositories).mockReturnValue(new Promise(() => {}));
    vi.mocked(getBranchRepositoryHealth).mockReturnValue(new Promise(() => {}));

    // WHEN
    const component = await renderCard();

    // THEN
    const status = component.getByRole("status");
    await expect.element(status).toHaveAttribute("aria-busy", "true");
    await expect.element(status).toHaveTextContent("Loading repositories");
    expect(status.element().querySelectorAll(".h-10")).toHaveLength(3);
    expect(component.container.querySelector("tbody")).toBeNull();
    expect(component.container.querySelector(".rounded-full")).toBeNull();
  });

  test("says the user has no access, with no rows and no count", async () => {
    // GIVEN
    vi.mocked(getBranchRepositories).mockRejectedValue(
      new BranchRepositoriesError("PERMISSION_DENIED", "You do not have one of the permissions")
    );
    vi.mocked(getBranchRepositoryHealth).mockReturnValue(new Promise(() => {}));

    // WHEN
    const component = await renderCard();

    // THEN
    await expect
      .element(component.getByText("You don't have access to this branch's repositories"))
      .toBeVisible();
    expect(component.container.querySelector("tbody")).toBeNull();
    expect(component.container.querySelector(".rounded-full")).toBeNull();
  });

  test("says the repositories couldn't be loaded, with the reason, when the query fails", async () => {
    // GIVEN
    vi.mocked(getBranchRepositories).mockRejectedValue(
      new BranchRepositoriesError("UNKNOWN", "Something broke")
    );
    vi.mocked(getBranchRepositoryHealth).mockReturnValue(new Promise(() => {}));

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("Repositories couldn't be loaded.")).toBeVisible();
    await expect.element(component.getByText("Something broke")).toBeVisible();
  });

  test("offers the first page when a later page fails, as the pager came with the page", async () => {
    // GIVEN
    const repositories = buildBranchRepositoriesScenario("eleven");
    serve(repositories);
    vi.mocked(getBranchRepositories).mockImplementation(async ({ offset, limit }) => {
      if (offset > 0) throw new BranchRepositoriesError("UNKNOWN", "Something broke");
      return toBranchRepositoryPage(repositories, { offset, limit });
    });
    const component = await renderCard({ search: "&repositories_page=2" });
    await expect.element(component.getByText("Repositories couldn't be loaded.")).toBeVisible();

    // WHEN
    await component.getByRole("button", { name: "Go to first page" }).click();

    // THEN
    await expect.poll(() => bodyRows(component.container)).toHaveLength(10);
    expect(new URL(window.location.href).searchParams.get("repositories_page")).toBeNull();
  });

  test("doesn't offer the first page when the first page fails", async () => {
    // GIVEN
    vi.mocked(getBranchRepositories).mockRejectedValue(
      new BranchRepositoriesError("UNKNOWN", "Something broke")
    );
    vi.mocked(getBranchRepositoryHealth).mockReturnValue(new Promise(() => {}));

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("Repositories couldn't be loaded.")).toBeVisible();
    expect(component.container.querySelector("button")).toBeNull();
  });

  test("says the repository health couldn't be checked, in place of the bands, while the table still shows", async () => {
    // GIVEN
    serve(buildBranchRepositoriesScenario("all-clear"));
    vi.mocked(getBranchRepositoryHealth).mockRejectedValue(new Error("Network error"));

    // WHEN
    const component = await renderCard();

    // THEN
    await expect
      .element(component.getByText("Repository health couldn't be checked."))
      .toBeVisible();
    expect(bodyRows(component.container)).toHaveLength(4);
    expect(
      component.container.querySelectorAll('[data-testid="repository-error-band"]')
    ).toHaveLength(0);
  });

  test("says the branch is not synchronised with Git when the server counts no repository and Sync with Git is off", async () => {
    // GIVEN
    serve(buildBranchRepositoriesScenario("no-repos"));

    // WHEN
    const component = await renderCard({ syncWithGit: false });

    // THEN
    await expect.element(component.getByText("Not synchronised with Git")).toBeVisible();
    await expect.element(component.getByText(/created with Sync with Git off/)).toBeVisible();
  });

  test("says no Git repositories are connected when the server counts none on a synced branch", async () => {
    // GIVEN
    serve(buildBranchRepositoriesScenario("no-repos"));

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("No Git repositories")).toBeVisible();
  });

  test("links repositories on the page's branch, not the selector's", async () => {
    // GIVEN
    serve(buildBranchRepositoriesScenario("all-clear"));

    // WHEN
    const component = await renderCard();

    // THEN
    await expect
      .element(component.getByRole("link", { name: "infrastructure-templates" }))
      .toHaveAttribute("href", "/objects/CoreRepository/repo-2?branch=feature");
  });

  test("flags unreachable repositories with an accessible warning icon", async () => {
    // GIVEN
    serve(buildBranchRepositoriesScenario("unreachable"));

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByRole("img", { name: "Credential Error" })).toBeVisible();
  });

  test("shows the unreachable reason in a tooltip on the warning icon", async () => {
    // GIVEN
    serve(buildBranchRepositoriesScenario("unreachable"));
    const component = await renderCard();

    // WHEN
    await initPointerTracking(component.locator);
    await component.getByRole("img", { name: "Credential Error" }).hover();

    // THEN
    await expect
      .element(component.getByRole("tooltip", { name: "Credential Error" }))
      .toBeVisible();
  });

  test("shows the raw sync status in a neutral tag when the schema has no label or colour", async () => {
    // GIVEN
    serve([
      generateBranchRepository({
        syncStatus: { value: "mystery", label: null, color: null, description: null },
        commit: null,
      }),
    ]);

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("mystery")).toBeVisible();
    await expect.element(component.getByText("—")).toBeVisible();
  });

  test("shows the server message in its failed state, with no toast, when the repositories request returns a GraphQL error", async () => {
    // GIVEN
    serve([]);
    const { getBranchRepositories: realGetBranchRepositories } = await vi.importActual<
      typeof import("@/entities/repository/domain/use-cases/get-branch-repositories")
    >("@/entities/repository/domain/use-cases/get-branch-repositories");
    vi.mocked(getBranchRepositories).mockImplementation(realGetBranchRepositories);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json({
          data: null,
          errors: [
            { message: "Repository index unavailable", extensions: { code: "NODE_NOT_FOUND" } },
          ],
        })
      )
    );

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("Repositories couldn't be loaded.")).toBeVisible();
    // A toast is emitted before the request rejects, so it would already be rendered by the time the card shows the error.
    await expect
      .poll(() =>
        page
          .getByRole("alert")
          .elements()
          .map((alert) => alert.textContent)
      )
      .toEqual(["Repositories couldn't be loaded.Repository index unavailable"]);
    await expect
      .element(component.getByText("Repository index unavailable", { exact: true }))
      .toBeVisible();
  });
});
