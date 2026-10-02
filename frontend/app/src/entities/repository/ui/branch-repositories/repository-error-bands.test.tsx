import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type {
  BranchRepository,
  BranchRepositoryHealth,
  RepositoryImportError,
} from "@/entities/repository/domain/model/branch-repository";
import { getBranchRepositories } from "@/entities/repository/domain/use-cases/get-branch-repositories";
import { getBranchRepositoryHealth } from "@/entities/repository/domain/use-cases/get-branch-repository-health";
import { useGetRepositoryImportError } from "@/entities/repository/ui/queries/get-repository-import-error.query";

import { render } from "../../../../../tests/components/render";
import {
  buildBranchRepositoriesScenario,
  generateBranchRepository,
  OPERATIONAL_STATUS,
  SYNC_STATUS,
  toBranchRepositoryHealth,
  toBranchRepositoryPage,
} from "../../../../../tests/fake/branch-repositories";
import { BranchRepositoriesCard } from "./branch-repositories-card";
import { RepositoryErrorBands } from "./repository-error-bands";

vi.mock("@/entities/repository/domain/use-cases/get-branch-repositories");
vi.mock("@/entities/repository/domain/use-cases/get-branch-repository-health");
vi.mock("@/entities/repository/ui/queries/get-repository-import-error.query");

const mockImportErrors = (byRepositoryId: Record<string, RepositoryImportError | undefined>) => {
  vi.mocked(useGetRepositoryImportError).mockImplementation(
    ({ repositoryId }) => byRepositoryId[repositoryId]
  );
};

const importErrorRepository = (id: string, overrides: Partial<BranchRepository> = {}) =>
  generateBranchRepository({ id, name: id, syncStatus: SYNC_STATUS.importError, ...overrides });

const unreachableRepository = (id: string) =>
  generateBranchRepository({ id, name: id, operationalStatus: OPERATIONAL_STATUS.errorCred });

const renderBands = (repositories: BranchRepository[]) =>
  render(
    <RepositoryErrorBands repositories={repositories} branchName="feature" isSyncing={false} />
  );

const bands = (container: HTMLElement) => [
  ...container.querySelectorAll('[data-testid="repository-error-band"]'),
];

const requestedRepositoryIds = () =>
  vi.mocked(useGetRepositoryImportError).mock.calls.map(([params]) => params.repositoryId);

describe("RepositoryErrorBands", () => {
  let initialUrl: string;

  beforeEach(() => {
    vi.clearAllMocks();
    mockImportErrors({});
    initialUrl = window.location.href;
    window.history.replaceState(null, "", "/branches/feature");
  });

  afterEach(() => {
    window.history.replaceState(null, "", initialUrl);
    document.documentElement.classList.remove("dark");
  });

  test("shows the last error line verbatim with a link to the task log", async () => {
    // GIVEN
    const message = "Traceback (most recent call last):\n  ValueError: invalid schema";
    mockImportErrors({ "network-services": { status: "found", taskId: "task-42", message } });

    // WHEN
    const component = await renderBands([importErrorRepository("network-services")]);

    // THEN
    await expect.element(component.getByText("network-services — import failed")).toBeVisible();
    const line = component.getByText(/ValueError: invalid schema/);
    expect(line.element().textContent).toBe(message);
    expect(line.element().className).toContain("whitespace-pre-wrap");
    expect(line.element().className).toContain("font-mono");
    await expect
      .element(component.getByRole("link", { name: "View task log →" }))
      .toHaveAttribute("href", "/tasks/task-42");
  });

  test("says the details couldn't be found and links to the repository when no task is found", async () => {
    // GIVEN
    window.history.replaceState(null, "", "/branches/feature?branch=main");
    mockImportErrors({ "repo-a": { status: "not-found", taskId: null } });

    // WHEN
    const component = await renderBands([importErrorRepository("repo-a")]);

    // THEN
    await expect
      .element(component.getByText("The error details couldn't be found for this import."))
      .toBeVisible();
    await expect
      .element(component.getByRole("link", { name: "Open repository" }))
      .toHaveAttribute("href", "/objects/CoreRepository/repo-a?branch=feature");
    expect(component.container.textContent).not.toContain("View task log");
  });

  test("still links to the task when it has no error line", async () => {
    // GIVEN
    mockImportErrors({ "repo-a": { status: "not-found", taskId: "task-7" } });

    // WHEN
    const component = await renderBands([importErrorRepository("repo-a")]);

    // THEN
    await expect
      .element(component.getByText("The error details couldn't be found for this import."))
      .toBeVisible();
    await expect
      .element(component.getByRole("link", { name: "View task log →" }))
      .toHaveAttribute("href", "/tasks/task-7");
  });

  test("warns that an unreachable repository's commit may be out of date", async () => {
    // GIVEN
    window.history.replaceState(null, "", "/branches/feature?branch=main");

    // WHEN
    const component = await renderBands([unreachableRepository("repo-b")]);

    // THEN
    await expect.element(component.getByText("repo-b — Credential Error")).toBeVisible();
    await expect
      .element(component.getByText(/Infrahub can't fetch new commits, so the commit shown/))
      .toBeVisible();
    await expect
      .element(component.getByRole("link", { name: "Open repository" }))
      .toHaveAttribute("href", "/objects/CoreRepository/repo-b?branch=feature");
    expect(useGetRepositoryImportError).not.toHaveBeenCalled();
  });

  test("shows 3 bands and a summary of the rest, then all of them on Show all", async () => {
    // GIVEN
    const repositories = [
      importErrorRepository("a"),
      importErrorRepository("b"),
      importErrorRepository("c"),
      importErrorRepository("d"),
      unreachableRepository("e"),
    ];
    const component = await renderBands(repositories);
    expect(bands(component.container)).toHaveLength(3);
    await expect
      .element(component.getByText("2 more repositories with errors: d, e"))
      .toBeVisible();

    // WHEN
    await component.getByRole("button", { name: "Show all" }).click();

    // THEN
    expect(bands(component.container)).toHaveLength(5);
    await expect.element(component.getByText("5 repositories with errors")).toBeVisible();
    await expect.element(component.getByRole("button", { name: "Collapse" })).toBeVisible();
  });

  test("uses the singular for one hidden repository", async () => {
    // WHEN
    const component = await renderBands(
      ["a", "b", "c", "d"].map((id) => importErrorRepository(id))
    );

    // THEN
    await expect.element(component.getByText("1 more repository with errors: d")).toBeVisible();
  });

  test("fetches the import log only for the visible bands until Show all", async () => {
    // GIVEN
    const repositories = ["a", "b", "c", "d", "e"].map((id) => importErrorRepository(id));
    const component = await renderBands(repositories);
    expect(new Set(requestedRepositoryIds())).toEqual(new Set(["a", "b", "c"]));

    // WHEN
    await component.getByRole("button", { name: "Show all" }).click();

    // THEN
    await expect.element(component.getByRole("button", { name: "Collapse" })).toBeVisible();
    expect(new Set(requestedRepositoryIds())).toEqual(new Set(["a", "b", "c", "d", "e"]));
  });

  test("shows the repository name and a loading line while the log loads", async () => {
    // WHEN
    const component = await renderBands([importErrorRepository("repo-a")]);

    // THEN
    await expect.element(component.getByText("repo-a — import failed")).toBeVisible();
    await expect.element(component.getByText("Loading the import log…")).toBeVisible();
    expect(component.container.querySelector("a")).toBeNull();
  });

  test("switches both band colours with the dark theme", async () => {
    // GIVEN
    mockImportErrors({
      "repo-a": { status: "found", taskId: "task-1", message: "ValueError: invalid schema" },
    });
    const component = await renderBands([
      importErrorRepository("repo-a"),
      unreachableRepository("repo-b"),
    ]);
    await expect.element(component.getByText("repo-a — import failed")).toBeVisible();
    const colours = () =>
      bands(component.container).map((band) => {
        const heading = band.querySelector(".font-semibold") ?? band;
        return [getComputedStyle(band).backgroundColor, getComputedStyle(heading).color];
      });
    const light = colours();

    // WHEN
    document.documentElement.classList.add("dark");

    // THEN
    const dark = colours().flat();
    const lightValues = light.flat();
    expect(dark).toHaveLength(4);
    dark.forEach((value, index) => {
      expect(value).not.toBe(lightValues[index]);
    });
  });

  test("renders nothing when no repository fails", async () => {
    // WHEN
    const component = await renderBands([]);

    // THEN
    expect(component.container.textContent).toBe("");
  });
});

describe("RepositoryErrorBands in the card", () => {
  let initialUrl: string;

  beforeEach(() => {
    vi.clearAllMocks();
    mockImportErrors({});
    initialUrl = window.location.href;
  });

  afterEach(() => {
    window.history.replaceState(null, "", initialUrl);
  });

  const serve = (
    repositories: BranchRepository[],
    health: BranchRepositoryHealth = toBranchRepositoryHealth(repositories)
  ) => {
    vi.mocked(getBranchRepositories).mockImplementation(async ({ offset, limit }) =>
      toBranchRepositoryPage(repositories, { offset, limit })
    );
    vi.mocked(getBranchRepositoryHealth).mockResolvedValue(health);
  };

  const card = (branchName = "feature") => (
    <BranchRepositoriesCard branchName={branchName} syncWithGit />
  );

  const renderCard = (search = "") => {
    window.history.replaceState(null, "", `/branches/feature${search}`);
    return render(card());
  };

  test("gives a repository that is both failing and unreachable one import error band", async () => {
    // GIVEN
    serve([importErrorRepository("both", { operationalStatus: OPERATIONAL_STATUS.errorCred })]);

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("both — import failed")).toBeVisible();
    expect(bands(component.container)).toHaveLength(1);
    await expect.element(component.getByRole("img", { name: "Credential Error" })).toBeVisible();
  });

  test("keeps the bands for failing repositories while another page of the table is shown", async () => {
    // GIVEN
    serve(buildBranchRepositoriesScenario("many-errors"));

    // WHEN
    const component = await renderCard("?repositories_page=3");

    // THEN
    await expect.element(component.getByText(/^2 more repositories with errors:/)).toBeVisible();
    const names = [...component.container.querySelectorAll("tbody tr a")].map(
      (link) => link.textContent
    );
    expect(names.some((name) => name?.includes("infrastructure-templates"))).toBe(false);
    expect(bands(component.container)).toHaveLength(3);
  });

  test("shows bands for failing repositories the server reports, even when none is on the page", async () => {
    // GIVEN
    const healthy = buildBranchRepositoriesScenario("all-clear");
    serve(healthy, {
      importErrors: [importErrorRepository("elsewhere")],
      unreachable: [],
      syncingCount: 0,
    });

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("elsewhere — import failed")).toBeVisible();
    expect(component.container.querySelector("tbody")?.textContent).not.toContain("elsewhere");
  });

  test("passes the syncing flag from the server's syncing count to the import error lookup", async () => {
    // GIVEN
    serve([
      importErrorRepository("a"),
      generateBranchRepository({ id: "s", name: "s", syncStatus: SYNC_STATUS.syncing }),
    ]);

    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("a — import failed")).toBeVisible();
    expect(useGetRepositoryImportError).toHaveBeenLastCalledWith(
      expect.objectContaining({ repositoryId: "a", branchName: "feature", isSyncing: true })
    );
  });

  test("collapses the bands again on another branch", async () => {
    // GIVEN
    serve(["a", "b", "c", "d"].map((id) => importErrorRepository(id)));
    const component = await renderCard();
    await component.getByRole("button", { name: "Show all" }).click();
    expect(bands(component.container)).toHaveLength(4);

    // WHEN
    await component.rerender(card("other-branch"));

    // THEN
    await expect.element(component.getByRole("button", { name: "Show all" })).toBeVisible();
    expect(bands(component.container)).toHaveLength(3);
  });
});
