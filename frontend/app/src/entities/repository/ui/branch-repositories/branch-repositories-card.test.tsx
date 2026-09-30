import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { page } from "vitest/browser";

import type { BranchRepositoriesResult } from "@/entities/repository/domain/model/branch-repository";
import { useGetBranchRepositories } from "@/entities/repository/ui/queries/get-branch-repositories.query";
import { useGetRepositoryImportError } from "@/entities/repository/ui/queries/get-repository-import-error.query";

import { render } from "../../../../../tests/components/render";
import {
  buildBranchRepositoriesScenario,
  generateBranchRepositoriesResult,
  generateBranchRepository,
  MANY_ERRORS_IMPORT_ERROR_POSITIONS,
  OPERATIONAL_STATUS,
  SYNC_STATUS,
} from "../../../../../tests/fake/branch-repositories";
import { BranchRepositoriesCard } from "./branch-repositories-card";

vi.mock("@/entities/repository/ui/queries/get-branch-repositories.query");
vi.mock("@/entities/repository/ui/queries/get-repository-import-error.query");

type QueryState = {
  data?: BranchRepositoriesResult;
  error?: Error;
  isPending?: boolean;
  isError?: boolean;
};

const mockQuery = ({ data, error, isPending = false, isError = false }: QueryState) => {
  vi.mocked(useGetBranchRepositories).mockReturnValue({
    data,
    error,
    isPending,
    isError,
  } as unknown as ReturnType<typeof useGetBranchRepositories>);
};

const renderCard = (props: Partial<Parameters<typeof BranchRepositoriesCard>[0]> = {}) =>
  render(
    <BranchRepositoriesCard
      branchName="feature"
      isDefaultBranch={false}
      syncWithGit
      page={1}
      onPageChange={vi.fn()}
      {...props}
    />
  );

const bodyRows = (container: HTMLElement) => [...container.querySelectorAll("tbody tr")];

const rowNames = (container: HTMLElement) =>
  bodyRows(container).map((row) => row.querySelector("a")?.textContent);

describe("BranchRepositoriesCard", () => {
  let initialUrl: string;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useGetRepositoryImportError).mockReturnValue({
      data: undefined,
    } as unknown as ReturnType<typeof useGetRepositoryImportError>);
    initialUrl = window.location.href;
    window.history.replaceState(null, "", "/branches/feature?branch=main");
  });

  afterEach(() => {
    window.history.replaceState(null, "", initialUrl);
    vi.unstubAllGlobals();
  });

  test("lists every repository with its Git state and commit, and the count in the header", async () => {
    // GIVEN
    mockQuery({ data: buildBranchRepositoriesScenario("all-clear") });

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("Git repositories")).toBeVisible();
    expect(bodyRows(component.container)).toHaveLength(4);
    await expect.element(component.getByText("4", { exact: true })).toBeVisible();
    await expect
      .element(component.getByRole("link", { name: "infrastructure-templates" }))
      .toBeVisible();
    await expect.element(component.getByText("In Sync").first()).toBeVisible();
    await expect.element(component.getByText("8f3c2a1")).toHaveAttribute("title", "8f3c2a1");
  });

  test("tags read-only repositories", async () => {
    // GIVEN
    mockQuery({ data: buildBranchRepositoriesScenario("all-clear") });

    // WHEN
    const component = await renderCard();

    // THEN
    const readOnlyRow = bodyRows(component.container).find((row) =>
      row.textContent?.includes("vendor-golden-configs")
    );
    expect(readOnlyRow?.textContent).toContain("Read-only");
    expect(component.container.textContent?.match(/Read-only/g)).toHaveLength(1);
  });

  test("puts every import-error repository on page 1, above the healthy ones", async () => {
    // GIVEN
    const data = buildBranchRepositoriesScenario("many-errors");
    mockQuery({ data });
    const failingNames =
      data.status === "ok"
        ? data.repositories
            .filter((repository) => repository.syncStatus.value === SYNC_STATUS.importError.value)
            .map((repository) => repository.name)
        : [];

    // WHEN
    const component = await renderCard();

    // THEN
    expect(failingNames).toHaveLength(MANY_ERRORS_IMPORT_ERROR_POSITIONS.length);
    const names = rowNames(component.container);
    expect(names).toHaveLength(10);
    expect([...names.slice(0, failingNames.length)].sort()).toEqual([...failingNames].sort());
  });

  test("keeps the table height on a short last page", async () => {
    // GIVEN
    mockQuery({ data: buildBranchRepositoriesScenario("eleven") });

    // WHEN
    const component = await renderCard({ page: 2 });

    // THEN
    expect(bodyRows(component.container)).toHaveLength(1);
    await expect
      .element(component.getByTestId("branch-repositories-table"))
      .toHaveStyle({ minHeight: "440px" });
    await expect.element(component.getByRole("navigation", { name: "Pagination" })).toBeVisible();
  });

  test("asks for the next page through the pager", async () => {
    // GIVEN
    const onPageChange = vi.fn();
    mockQuery({ data: buildBranchRepositoriesScenario("eleven") });
    const component = await renderCard({ onPageChange });

    // WHEN
    await component.getByRole("button", { name: "Next page" }).click();

    // THEN
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  test("shows the last page and writes it back for a page past the end", async () => {
    // GIVEN
    const onPageChange = vi.fn();
    mockQuery({ data: buildBranchRepositoriesScenario("eleven") });

    // WHEN
    const component = await renderCard({ page: 99, onPageChange });

    // THEN
    expect(bodyRows(component.container)).toHaveLength(1);
    await expect
      .element(component.getByRole("button", { name: "Page 2" }))
      .toHaveAttribute("aria-current", "page");
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  test("shows page 1 and writes it back for a page below 1", async () => {
    // GIVEN
    const onPageChange = vi.fn();
    mockQuery({ data: buildBranchRepositoriesScenario("eleven") });

    // WHEN
    const component = await renderCard({ page: 0, onPageChange });

    // THEN
    expect(bodyRows(component.container)).toHaveLength(10);
    await expect
      .element(component.getByRole("button", { name: "Page 1" }))
      .toHaveAttribute("aria-current", "page");
    expect(onPageChange).toHaveBeenCalledWith(1);
  });

  test("shows all 10 rows and no pager for exactly 10 repositories", async () => {
    // GIVEN
    mockQuery({ data: buildBranchRepositoriesScenario("exactly-10") });

    // WHEN
    const component = await renderCard();

    // THEN
    expect(bodyRows(component.container)).toHaveLength(10);
    expect(component.container.querySelector("nav")).toBeNull();
    await expect
      .element(component.getByTestId("branch-repositories-table"))
      .not.toHaveAttribute("style");
  });

  test("shows placeholder rows and no count while loading", async () => {
    // GIVEN
    mockQuery({ isPending: true });

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
    mockQuery({ data: { status: "denied" } });

    // WHEN
    const component = await renderCard();

    // THEN
    await expect
      .element(component.getByText("You don't have access to this branch's repositories"))
      .toBeVisible();
    expect(component.container.querySelector("tbody")).toBeNull();
    expect(component.container.querySelector(".rounded-full")).toBeNull();
  });

  test("says the branch is not synchronised with Git when Sync with Git is off", async () => {
    // GIVEN
    mockQuery({ data: buildBranchRepositoriesScenario("no-repos") });

    // WHEN
    const component = await renderCard({ syncWithGit: false });

    // THEN
    await expect.element(component.getByText("Not synchronised with Git")).toBeVisible();
    await expect.element(component.getByText(/created with Sync with Git off/)).toBeVisible();
  });

  test("says no Git repositories are connected on a synced branch", async () => {
    // GIVEN
    mockQuery({ data: buildBranchRepositoriesScenario("no-repos") });

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("No Git repositories")).toBeVisible();
  });

  test("says the repositories couldn't be loaded, with the reason, when the query fails", async () => {
    // GIVEN
    mockQuery({ isError: true, error: new Error("Repository index unavailable") });

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("Repositories couldn't be loaded.")).toBeVisible();
    await expect.element(component.getByText("Repository index unavailable")).toBeVisible();
  });

  test("links repositories on the page's branch, not the selector's", async () => {
    // GIVEN
    mockQuery({ data: buildBranchRepositoriesScenario("all-clear") });

    // WHEN
    const component = await renderCard();

    // THEN
    await expect
      .element(component.getByRole("link", { name: "infrastructure-templates" }))
      .toHaveAttribute("href", "/objects/CoreRepository/repo-2?branch=feature");
  });

  test("drops the branch parameter on the default branch", async () => {
    // GIVEN
    mockQuery({ data: buildBranchRepositoriesScenario("all-clear") });

    // WHEN
    const component = await renderCard({ branchName: "main", isDefaultBranch: true });

    // THEN
    await expect
      .element(component.getByRole("link", { name: "infrastructure-templates" }))
      .toHaveAttribute("href", "/objects/CoreRepository/repo-2");
  });

  test("flags unreachable repositories with an accessible warning icon", async () => {
    // GIVEN
    mockQuery({ data: buildBranchRepositoriesScenario("unreachable") });

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByRole("img", { name: "Credential Error" })).toBeVisible();
  });

  test("shows the raw sync status in a neutral tag when the schema has no label or colour", async () => {
    // GIVEN
    mockQuery({
      data: generateBranchRepositoriesResult([
        generateBranchRepository({
          syncStatus: { value: "mystery", label: null, color: null, description: null },
          commit: null,
        }),
      ]),
    });

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("mystery")).toBeVisible();
    await expect.element(component.getByText("—")).toBeVisible();
  });

  test("tells the user when the list is truncated", async () => {
    // GIVEN
    mockQuery({
      data: generateBranchRepositoriesResult([generateBranchRepository()], 600),
    });

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText(/Showing the first 1 of 600/)).toBeVisible();
    await expect
      .element(component.getByRole("link", { name: "View all repositories" }))
      .toHaveAttribute("href", "/objects/CoreGenericRepository?branch=feature");
  });

  test("links the truncation notice to the read-only list when Sync with Git is off", async () => {
    // GIVEN
    mockQuery({
      data: generateBranchRepositoriesResult(
        [generateBranchRepository({ kind: "CoreReadOnlyRepository" })],
        600
      ),
    });

    // WHEN
    const component = await renderCard({ syncWithGit: false });

    // THEN
    await expect
      .element(component.getByRole("link", { name: "View all repositories" }))
      .toHaveAttribute("href", "/objects/CoreReadOnlyRepository?branch=feature");
  });

  test("uses no hard-coded hex colour in class names", async () => {
    // GIVEN
    mockQuery({
      data: generateBranchRepositoriesResult([
        generateBranchRepository({ id: "a", name: "a", syncStatus: SYNC_STATUS.importError }),
        generateBranchRepository({
          id: "b",
          name: "b",
          isReadOnly: true,
          operationalStatus: OPERATIONAL_STATUS.errorCred,
        }),
      ]),
    });

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("Import Error")).toBeVisible();
    const classes = [...component.container.querySelectorAll("[class]")].map(
      (element) => element.getAttribute("class") ?? ""
    );
    expect(classes.filter((value) => /#[0-9a-f]{3,8}\b/i.test(value))).toEqual([]);
  });

  test("shows the server message in its failed state, with no toast, when the repositories request returns a GraphQL error", async () => {
    // GIVEN
    const { useGetBranchRepositories: realUseGetBranchRepositories } = await vi.importActual<
      typeof import("@/entities/repository/ui/queries/get-branch-repositories.query")
    >("@/entities/repository/ui/queries/get-branch-repositories.query");
    vi.mocked(useGetBranchRepositories).mockImplementation(realUseGetBranchRepositories);
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
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(
      page
        .getByRole("alert")
        .elements()
        .map((alert) => alert.textContent)
    ).toEqual(["Repositories couldn't be loaded.Repository index unavailable"]);
    await expect
      .element(component.getByText("Repository index unavailable", { exact: true }))
      .toBeVisible();
  });
});
