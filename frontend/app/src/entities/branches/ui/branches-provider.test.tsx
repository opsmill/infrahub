import { beforeEach, describe, expect, test, vi } from "vitest";

import { QSP } from "@/shared/config/qsp";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import { BranchesProvider, useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";

import { render } from "../../../../tests/components/render";
import { generateBranch } from "../../../../tests/fake/branch";

vi.mock("@/entities/branches/ui/queries/get-branches.query");

// Deliberately not named "main": INFRAHUB_INITIAL_DEFAULT_BRANCH can rename the default branch,
// so the provider has to resolve it from is_default.
const defaultBranch = generateBranch({ id: "branch-default", name: "primary", is_default: true });
const featureBranch = generateBranch({ id: "branch-feature", name: "feature-1" });

const mockBranchesQuery = (state: Partial<ReturnType<typeof useGetBranches>>) =>
  vi.mocked(useGetBranches).mockReturnValue(state as ReturnType<typeof useGetBranches>);

const mockFetchedBranches = () =>
  mockBranchesQuery({ data: [defaultBranch, featureBranch], isPending: false, error: null });

const seedBranchInUrl = (branchName: string) =>
  window.history.replaceState(null, "", `${window.location.pathname}?${QSP.BRANCH}=${branchName}`);

const getBranchInUrl = () => new URLSearchParams(window.location.search).get(QSP.BRANCH);

function BranchProbe({ switchTo }: { switchTo?: BranchListItem }) {
  const { currentBranch, setCurrentBranch } = useCurrentBranch();

  return (
    <>
      <p>Current branch: {currentBranch.name}</p>

      {switchTo && (
        <button type="button" onClick={() => setCurrentBranch(switchTo)}>
          Switch branch
        </button>
      )}
    </>
  );
}

describe("BranchesProvider", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", window.location.pathname);
  });

  test("resolves the default branch when the URL has no branch", async () => {
    // GIVEN
    mockFetchedBranches();

    // WHEN
    const component = await render(
      <BranchesProvider>
        <BranchProbe />
      </BranchesProvider>
    );

    // THEN
    await expect.element(component.getByText("Current branch: primary")).toBeVisible();
  });

  test("resolves the branch named in the URL", async () => {
    // GIVEN
    mockFetchedBranches();
    seedBranchInUrl(featureBranch.name);

    // WHEN
    const component = await render(
      <BranchesProvider>
        <BranchProbe />
      </BranchesProvider>
    );

    // THEN
    await expect.element(component.getByText("Current branch: feature-1")).toBeVisible();
  });

  test("resolves the default branch when the URL names it explicitly", async () => {
    // GIVEN
    mockFetchedBranches();
    seedBranchInUrl(defaultBranch.name);

    // WHEN
    const component = await render(
      <BranchesProvider>
        <BranchProbe />
      </BranchesProvider>
    );

    // THEN
    await expect.element(component.getByText("Current branch: primary")).toBeVisible();
    expect(getBranchInUrl()).toBe("primary");
  });

  test("hides its children while the branches are being fetched", async () => {
    // GIVEN
    mockBranchesQuery({ isPending: true, error: null });

    // WHEN
    const component = await render(
      <BranchesProvider>
        <BranchProbe />
      </BranchesProvider>
    );

    // THEN
    await expect.element(component.getByText("Loading branches...")).toBeVisible();
    expect(component.getByText(/Current branch/).query()).toBeNull();
  });

  test("keeps its children mounted while the branches are refetched in the background", async () => {
    // GIVEN
    mockBranchesQuery({
      data: [defaultBranch, featureBranch],
      isPending: false,
      isFetching: true,
      error: null,
    });

    // WHEN
    const component = await render(
      <BranchesProvider>
        <BranchProbe />
      </BranchesProvider>
    );

    // THEN
    await expect.element(component.getByText("Current branch: primary")).toBeVisible();
    expect(component.getByText("Loading branches...").query()).toBeNull();
  });

  test("shows an error screen when the branches cannot be fetched", async () => {
    // GIVEN
    mockBranchesQuery({ isPending: false, error: new Error("Branches are unreachable") });

    // WHEN
    const component = await render(
      <BranchesProvider>
        <BranchProbe />
      </BranchesProvider>
    );

    // THEN
    await expect.element(component.getByText("Branches are unreachable")).toBeVisible();
  });

  test("drops the branch parameter when switching to the default branch", async () => {
    // GIVEN
    mockFetchedBranches();
    seedBranchInUrl(featureBranch.name);
    const component = await render(
      <BranchesProvider>
        <BranchProbe switchTo={defaultBranch} />
      </BranchesProvider>
    );

    // WHEN
    await component.getByRole("button", { name: "Switch branch" }).click();

    // THEN
    await expect.poll(getBranchInUrl).toBeNull();
  });

  test("writes the branch name when switching to a non-default branch", async () => {
    // GIVEN
    mockFetchedBranches();
    const component = await render(
      <BranchesProvider>
        <BranchProbe switchTo={featureBranch} />
      </BranchesProvider>
    );

    // WHEN
    await component.getByRole("button", { name: "Switch branch" }).click();

    // THEN
    await expect.poll(getBranchInUrl).toBe("feature-1");
  });

  test("falls back to the default branch when the URL names an unknown branch", async () => {
    // GIVEN
    mockFetchedBranches();
    seedBranchInUrl("does-not-exist");

    // WHEN
    const component = await render(
      <BranchesProvider>
        <BranchProbe />
      </BranchesProvider>
    );

    // THEN
    await expect
      .element(component.getByText(/not found, you have been redirected to the main branch/))
      .toBeVisible();
    await expect.poll(getBranchInUrl).toBeNull();
  });
});
