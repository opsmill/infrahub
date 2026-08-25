import React from "react";
import { MemoryRouter, useLocation } from "react-router";
import { toast } from "react-toastify";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import {
  type BranchListConfirmation,
  confirmsBranchIsGone,
  useRedirectWhenBranchIsGone,
} from "@/entities/branches/ui/hooks/use-redirect-when-branch-is-gone";
import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";

import { generateBranch } from "../../../../../tests/fake/branch";

vi.mock("@/entities/branches/ui/queries/get-branches.query");

vi.mock("react-toastify", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react-toastify")>()),
  toast: vi.fn(),
}));

const defaultBranch = generateBranch({ id: "branch-default", name: "primary", is_default: true });
const featureBranch = generateBranch({ id: "branch-feature", name: "feature-1" });
const otherBranch = generateBranch({ id: "branch-other", name: "feature-2" });

const withoutFeature = [defaultBranch, otherBranch];
const withFeature = [defaultBranch, otherBranch, featureBranch];
const withoutDefault = [featureBranch, otherBranch];

const confirmsGone: BranchListConfirmation = { data: withoutFeature, isError: false };
const confirmsBack: BranchListConfirmation = { data: withFeature, isError: false };
const failedFetch: BranchListConfirmation = { data: undefined, isError: true };

const STARTING_PAGE = "/objects/device";

type ScriptedRefetch =
  | { data: BranchListItem[] }
  | { isError: true }
  | { rejects: true }
  | { heldData: BranchListItem[] };

// Mocks useGetBranches the way React Query behaves: refetch is a stable function that resolves with
// the next scripted response and re-renders with it, dataUpdatedAt bumps only on fresh data, and
// arriveList models a background refresh (window focus, mutation) landing outside any refetch call.
const mockBranchesQuery = (initial: BranchListItem[] | undefined, ...script: ScriptedRefetch[]) => {
  let setQueryState!: React.Dispatch<
    React.SetStateAction<{ data: BranchListItem[] | undefined; dataUpdatedAt: number }>
  >;
  let releaseHeld: (() => void) | undefined;

  const applyList = (data: BranchListItem[]) =>
    setQueryState((state) => ({ data, dataUpdatedAt: state.dataUpdatedAt + 1 }));

  const refetch = vi.fn(() => {
    const response = script.length > 1 ? script.shift()! : script[0]!;
    if ("rejects" in response) return Promise.reject(new Error("network is down"));
    if ("isError" in response) return Promise.resolve(failedFetch);
    if ("heldData" in response) {
      return new Promise<BranchListConfirmation>((resolve) => {
        releaseHeld = () => {
          applyList(response.heldData);
          resolve({ data: response.heldData, isError: false });
        };
      });
    }
    applyList(response.data);
    return Promise.resolve({ data: response.data, isError: false });
  });

  vi.mocked(useGetBranches).mockImplementation(() => {
    const [queryState, setState] = React.useState({
      data: initial,
      dataUpdatedAt: initial ? 1 : 0,
    });
    setQueryState = setState;

    return { ...queryState, refetch } as unknown as ReturnType<typeof useGetBranches>;
  });

  return {
    refetch,
    arriveList: (data: BranchListItem[]) => applyList(data),
    releaseHeldRefetch: () => releaseHeld?.(),
    heldRefetchStarted: () => releaseHeld !== undefined,
  };
};

const wrapper = ({ children }: { children?: React.ReactNode }) => (
  <MemoryRouter initialEntries={[STARTING_PAGE]}>{children}</MemoryRouter>
);

const renderRedirect = (branchName: string | null) =>
  renderHook(
    (props?: { branchName: string | null }) => {
      const { isDefaultBranchGone } = useRedirectWhenBranchIsGone({
        branchName: props ? props.branchName : branchName,
      });
      return { pathname: useLocation().pathname, isDefaultBranchGone };
    },
    { wrapper, initialProps: { branchName } }
  );

// A nothing-happened assertion has no signal to poll for, so let pending effects run first.
const settle = () => new Promise((resolve) => setTimeout(resolve, 50));

const toastCount = () => vi.mocked(toast).mock.calls.length;

describe("confirmsBranchIsGone", () => {
  test("confirms a branch the freshly fetched list does not contain", () => {
    expect(confirmsBranchIsGone(confirmsGone, "feature-1")).toBe(true);
  });

  test("clears a branch the freshly fetched list does contain", () => {
    expect(confirmsBranchIsGone(confirmsBack, "feature-1")).toBe(false);
  });

  test("confirms nothing when the fetch failed", () => {
    expect(confirmsBranchIsGone(failedFetch, "feature-1")).toBe(false);
  });

  test("clears the default branch while the list carries one", () => {
    expect(confirmsBranchIsGone(confirmsGone, null)).toBe(false);
  });

  test("confirms the default branch gone when the list carries none", () => {
    expect(confirmsBranchIsGone({ data: withoutDefault, isError: false }, null)).toBe(true);
  });
});

describe("useRedirectWhenBranchIsGone", () => {
  beforeEach(() => {
    vi.mocked(toast).mockClear();
  });

  test("redirects once a second fetch also misses the branch", async () => {
    // GIVEN
    mockBranchesQuery(withoutFeature, { data: withoutFeature });

    // WHEN
    const { result } = await renderRedirect("feature-1");

    // THEN
    await expect.poll(() => result.current.pathname).toBe("/");
    await settle();
    expect(toast).toHaveBeenCalledOnce();
  });

  test("stays put when the branch is back in the freshly fetched list", async () => {
    // GIVEN
    const { refetch } = mockBranchesQuery(withoutFeature, { data: withFeature });

    // WHEN
    const { result } = await renderRedirect("feature-1");

    // THEN
    await expect.poll(() => refetch.mock.calls.length).toBe(1);
    await settle();
    expect(result.current.pathname).toBe(STARTING_PAGE);
    expect(toast).not.toHaveBeenCalled();
  });

  test("stays put when the confirming fetch fails", async () => {
    // GIVEN
    const { refetch } = mockBranchesQuery(withoutFeature, { isError: true });

    // WHEN
    const { result } = await renderRedirect("feature-1");

    // THEN
    await expect.poll(() => refetch.mock.calls.length).toBe(1);
    await settle();
    expect(result.current.pathname).toBe(STARTING_PAGE);
  });

  test("stays put when the confirming fetch rejects", async () => {
    // GIVEN
    const { refetch } = mockBranchesQuery(withoutFeature, { rejects: true });

    // WHEN
    const { result } = await renderRedirect("feature-1");

    // THEN
    await expect.poll(() => refetch.mock.calls.length).toBe(1);
    await settle();
    expect(result.current.pathname).toBe(STARTING_PAGE);
  });

  test("re-confirms when a later list still omits the branch after a failed confirmation", async () => {
    // GIVEN a first confirmation that failed, leaving the miss unconfirmed
    const { refetch, arriveList } = mockBranchesQuery(
      withoutFeature,
      { rejects: true },
      { data: withoutFeature }
    );
    const { result } = await renderRedirect("feature-1");
    await expect.poll(() => refetch.mock.calls.length).toBe(1);

    // WHEN a background refresh lands and the branch is still missing
    arriveList(withoutFeature);

    // THEN the miss is confirmed again and the redirect happens exactly once
    await expect.poll(() => result.current.pathname).toBe("/");
    await settle();
    expect(refetch).toHaveBeenCalledTimes(2);
    expect(toast).toHaveBeenCalledOnce();
  });

  test("does not confirm anything while the branch is in the list", async () => {
    // GIVEN
    const { refetch } = mockBranchesQuery(withFeature, { data: withFeature });

    // WHEN
    const { result } = await renderRedirect("feature-1");

    // THEN
    await settle();
    expect(refetch).not.toHaveBeenCalled();
    expect(result.current.pathname).toBe(STARTING_PAGE);
  });

  test("does not confirm anything before the first list arrives", async () => {
    // GIVEN
    const { refetch } = mockBranchesQuery(undefined, { data: withoutFeature });

    // WHEN
    await renderRedirect("feature-1");

    // THEN
    await settle();
    expect(refetch).not.toHaveBeenCalled();
  });

  test("does not apply a verdict to the branch the user moved on to", async () => {
    // GIVEN a confirmation for feature-1 held in flight
    const { heldRefetchStarted, releaseHeldRefetch } = mockBranchesQuery(withoutFeature, {
      heldData: withoutFeature,
    });
    const { result, rerender } = await renderRedirect("feature-1");
    await expect.poll(heldRefetchStarted).toBe(true);

    // WHEN the user moves to a branch that resolves, and only then does the verdict land
    await rerender({ branchName: "feature-2" });
    releaseHeldRefetch();

    // THEN
    await settle();
    expect(result.current.pathname).toBe(STARTING_PAGE);
    expect(toast).not.toHaveBeenCalled();
  });

  test("redirects again on a revisit without asking the server twice", async () => {
    // GIVEN a branch already confirmed gone and redirected away from
    const { refetch } = mockBranchesQuery(withoutFeature, { data: withoutFeature });
    const { rerender } = await renderRedirect("feature-1");
    await expect.poll(toastCount).toBe(1);
    await rerender({ branchName: null });

    // WHEN the same name comes back, e.g. the user hits back
    await rerender({ branchName: "feature-1" });

    // THEN it redirects on the standing verdict rather than confirming again
    await expect.poll(toastCount).toBe(2);
    expect(refetch).toHaveBeenCalledOnce();
  });

  test("re-confirms a name the list carries again, whichever branch is selected", async () => {
    // GIVEN feature-1 was confirmed gone, then recreated while the user sat on another branch
    const { refetch, arriveList } = mockBranchesQuery(
      withoutFeature,
      { data: withoutFeature },
      { data: withFeature }
    );
    const { rerender } = await renderRedirect("feature-1");
    await expect.poll(toastCount).toBe(1);
    await rerender({ branchName: "feature-2" });
    arriveList(withFeature);
    await settle();

    // WHEN the user lands on it while a fetched list transiently omits it again
    arriveList(withoutFeature);
    await rerender({ branchName: "feature-1" });

    // THEN the miss is confirmed afresh instead of reusing the standing verdict
    await expect.poll(() => refetch.mock.calls.length).toBe(2);
    await settle();
    expect(toastCount()).toBe(1);
  });

  test("reports the default branch gone instead of redirecting, and recovers when it is back", async () => {
    // GIVEN a list with no default branch, on the default branch (no name in the URL)
    const { arriveList } = mockBranchesQuery(withoutDefault, { data: withoutDefault });

    // WHEN
    const { result } = await renderRedirect(null);

    // THEN the confirmed miss is reported, with no redirect and no toast
    await expect.poll(() => result.current.isDefaultBranchGone).toBe(true);
    expect(result.current.pathname).toBe(STARTING_PAGE);
    expect(toast).not.toHaveBeenCalled();

    // WHEN a list carries a default branch again
    arriveList(withFeature);

    // THEN the report clears
    await expect.poll(() => result.current.isDefaultBranchGone).toBe(false);
  });

  test("does not report the default branch gone when the confirming fetch carries it", async () => {
    // GIVEN a single list omitting the default branch, while the server still has one
    const { refetch } = mockBranchesQuery(withoutDefault, { data: withFeature });

    // WHEN
    const { result } = await renderRedirect(null);

    // THEN
    await expect.poll(() => refetch.mock.calls.length).toBe(1);
    await settle();
    expect(result.current.isDefaultBranchGone).toBe(false);
  });
});
