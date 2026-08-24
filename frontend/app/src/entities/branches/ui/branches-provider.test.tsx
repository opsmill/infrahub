import React from "react";
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
const otherBranch = generateBranch({ id: "branch-other", name: "feature-2" });

type BranchesQueryState = Partial<ReturnType<typeof useGetBranches>>;

// Mocked as a hook rather than a fixed value so that refetch() behaves like React Query's: it
// resolves with the next scripted response and re-renders with it. Responses are consumed in order
// and the last one is reused once the script runs out.
const mockBranchesQuery = (...responses: BranchesQueryState[]) =>
  vi.mocked(useGetBranches).mockImplementation(() => {
    const [fetchIndex, setFetchIndex] = React.useState(0);
    const lastIndex = responses.length - 1;

    return {
      ...responses[Math.min(fetchIndex, lastIndex)],
      refetch: () => {
        const nextIndex = Math.min(fetchIndex + 1, lastIndex);
        setFetchIndex(nextIndex);
        return Promise.resolve(responses[nextIndex]);
      },
    } as ReturnType<typeof useGetBranches>;
  });

// Scripts a single list plus a refetch the test releases by hand, so a confirmation can be held
// in flight while the URL moves to another branch.
const mockBranchesQueryWithHeldRefetch = (branches: BranchListItem[]) => {
  let release: (() => void) | undefined;

  vi.mocked(useGetBranches).mockImplementation(
    () =>
      ({
        data: branches,
        isPending: false,
        error: null,
        refetch: () =>
          new Promise((resolve) => {
            release = () => resolve({ data: branches, isError: false });
          }),
      }) as unknown as ReturnType<typeof useGetBranches>
  );

  return {
    isRefetching: () => release !== undefined,
    releaseRefetch: () => release?.(),
  };
};

const mockFetchedBranches = () =>
  mockBranchesQuery({ data: [defaultBranch, featureBranch], isPending: false, error: null });

const seedBranchInUrl = (branchName: string) =>
  window.history.replaceState(null, "", `${window.location.pathname}?${QSP.BRANCH}=${branchName}`);

const getBranchInUrl = () => new URLSearchParams(window.location.search).get(QSP.BRANCH);

// The provider renders a spinner instead of its children while the branch is unresolved, so a user
// mid-confirmation can only move by navigating (back/forward, a link), not by using the selector.
const navigateToBranchInUrl = (branchName: string) => {
  seedBranchInUrl(branchName);
  window.dispatchEvent(new PopStateEvent("popstate"));
};

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

  test("stays on the branch when only one fetched list omitted it", async () => {
    // GIVEN
    mockBranchesQuery(
      { data: [defaultBranch], isPending: false, error: null },
      { data: [defaultBranch, featureBranch], isPending: false, error: null }
    );
    seedBranchInUrl(featureBranch.name);

    // WHEN
    const component = await render(
      <BranchesProvider>
        <BranchProbe />
      </BranchesProvider>
    );

    // THEN
    await expect.element(component.getByText("Current branch: feature-1")).toBeVisible();
    expect(getBranchInUrl()).toBe("feature-1");
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
      .element(component.getByText(/not found, you have been redirected to the default branch/))
      .toBeVisible();
    await expect.poll(getBranchInUrl).toBeNull();
  });

  test("redirects again when the same unknown branch is visited a second time", async () => {
    // GIVEN a branch that is gone, already redirected away from once
    mockFetchedBranches();
    seedBranchInUrl("does-not-exist");
    const component = await render(
      <BranchesProvider>
        <BranchProbe />
      </BranchesProvider>
    );
    await expect.poll(getBranchInUrl).toBeNull();

    // WHEN the same name comes back into the URL, e.g. the user hits back
    navigateToBranchInUrl("does-not-exist");

    // THEN it redirects again rather than leaving the app on a spinner it never leaves
    await expect.poll(getBranchInUrl).toBeNull();
    await expect.element(component.getByText("Current branch: primary")).toBeVisible();
  });

  test("does not redirect a user who moved on while the confirmation was in flight", async () => {
    // GIVEN feature-1 is gone, feature-2 is live, and feature-1's confirmation is held in flight
    const { isRefetching, releaseRefetch } = mockBranchesQueryWithHeldRefetch([
      defaultBranch,
      otherBranch,
    ]);
    seedBranchInUrl(featureBranch.name);
    const component = await render(
      <BranchesProvider>
        <BranchProbe />
      </BranchesProvider>
    );
    await expect.poll(isRefetching).toBe(true);

    // WHEN the user moves to feature-2 and only then does the feature-1 confirmation land
    navigateToBranchInUrl(otherBranch.name);
    await expect.element(component.getByText("Current branch: feature-2")).toBeVisible();
    releaseRefetch();

    // THEN feature-1's verdict is not applied to feature-2
    await expect.poll(getBranchInUrl).toBe("feature-2");
    expect(
      component.getByText(/not found, you have been redirected to the default branch/).query()
    ).toBeNull();
  });
});
