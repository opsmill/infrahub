import type React from "react";
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

import { generateBranch } from "../../../../../tests/fake/branch";

vi.mock("react-toastify", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react-toastify")>()),
  toast: vi.fn(),
}));

const defaultBranch = generateBranch({ id: "branch-default", name: "primary", is_default: true });
const featureBranch = generateBranch({ id: "branch-feature", name: "feature-1" });
const otherBranch = generateBranch({ id: "branch-other", name: "feature-2" });

const withoutFeature = [defaultBranch, otherBranch];
const withFeature = [defaultBranch, otherBranch, featureBranch];

const confirmsGone: BranchListConfirmation = { data: withoutFeature, isError: false };
const confirmsBack: BranchListConfirmation = { data: withFeature, isError: false };
const failedFetch: BranchListConfirmation = { data: undefined, isError: true };

const STARTING_PAGE = "/objects/device";

type Props = { branchName: string | null; branches: BranchListItem[] | undefined };

const wrapper = ({ children }: { children?: React.ReactNode }) => (
  <MemoryRouter initialEntries={[STARTING_PAGE]}>{children}</MemoryRouter>
);

const renderRedirect = (
  initialProps: Props,
  confirmBranchList: () => Promise<BranchListConfirmation>
) =>
  renderHook(
    (props?: Props) => {
      useRedirectWhenBranchIsGone({ ...initialProps, ...props, confirmBranchList });
      return useLocation().pathname;
    },
    { wrapper, initialProps }
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

  test("never confirms an unnamed branch, which resolves to the default one", () => {
    expect(confirmsBranchIsGone(confirmsGone, null)).toBe(false);
  });
});

describe("useRedirectWhenBranchIsGone", () => {
  beforeEach(() => {
    vi.mocked(toast).mockClear();
  });

  test("redirects once a second fetch also misses the branch", async () => {
    // GIVEN
    const confirmBranchList = vi.fn().mockResolvedValue(confirmsGone);

    // WHEN
    const { result } = await renderRedirect(
      { branchName: "feature-1", branches: withoutFeature },
      confirmBranchList
    );

    // THEN
    await expect.poll(() => result.current).toBe("/");
    expect(toast).toHaveBeenCalledOnce();
  });

  test("stays put when the branch is back in the freshly fetched list", async () => {
    // GIVEN
    const confirmBranchList = vi.fn().mockResolvedValue(confirmsBack);

    // WHEN
    const { result } = await renderRedirect(
      { branchName: "feature-1", branches: withoutFeature },
      confirmBranchList
    );

    // THEN
    await expect.poll(() => confirmBranchList.mock.calls.length).toBe(1);
    await settle();
    expect(result.current).toBe(STARTING_PAGE);
    expect(toast).not.toHaveBeenCalled();
  });

  test("stays put when the confirming fetch fails", async () => {
    // GIVEN
    const confirmBranchList = vi.fn().mockResolvedValue(failedFetch);

    // WHEN
    const { result } = await renderRedirect(
      { branchName: "feature-1", branches: withoutFeature },
      confirmBranchList
    );

    // THEN
    await expect.poll(() => confirmBranchList.mock.calls.length).toBe(1);
    await settle();
    expect(result.current).toBe(STARTING_PAGE);
  });

  test("stays put when the confirming fetch rejects", async () => {
    // GIVEN
    const confirmBranchList = vi.fn().mockRejectedValue(new Error("network is down"));

    // WHEN
    const { result } = await renderRedirect(
      { branchName: "feature-1", branches: withoutFeature },
      confirmBranchList
    );

    // THEN
    await expect.poll(() => confirmBranchList.mock.calls.length).toBe(1);
    await settle();
    expect(result.current).toBe(STARTING_PAGE);
  });

  test("does not confirm anything while the branch is in the list", async () => {
    // GIVEN
    const confirmBranchList = vi.fn().mockResolvedValue(confirmsGone);

    // WHEN
    const { result } = await renderRedirect(
      { branchName: "feature-1", branches: withFeature },
      confirmBranchList
    );

    // THEN
    await settle();
    expect(confirmBranchList).not.toHaveBeenCalled();
    expect(result.current).toBe(STARTING_PAGE);
  });

  test("does not confirm anything before the first list arrives", async () => {
    // GIVEN
    const confirmBranchList = vi.fn().mockResolvedValue(confirmsGone);

    // WHEN
    await renderRedirect({ branchName: "feature-1", branches: undefined }, confirmBranchList);

    // THEN
    await settle();
    expect(confirmBranchList).not.toHaveBeenCalled();
  });

  test("does not apply a verdict to the branch the user moved on to", async () => {
    // GIVEN a confirmation for feature-1 held in flight
    let release: (() => void) | undefined;
    const confirmBranchList = vi.fn(
      () =>
        new Promise<BranchListConfirmation>((resolve) => {
          release = () => resolve(confirmsGone);
        })
    );
    const { result, rerender } = await renderRedirect(
      { branchName: "feature-1", branches: withoutFeature },
      confirmBranchList
    );
    await expect.poll(() => release !== undefined).toBe(true);

    // WHEN the user moves to a branch that resolves, and only then does the verdict land
    await rerender({ branchName: "feature-2", branches: withoutFeature });
    release?.();

    // THEN
    await settle();
    expect(result.current).toBe(STARTING_PAGE);
    expect(toast).not.toHaveBeenCalled();
  });

  test("redirects again on a revisit without asking the server twice", async () => {
    // GIVEN a branch already confirmed gone and redirected away from
    const confirmBranchList = vi.fn().mockResolvedValue(confirmsGone);
    const { rerender } = await renderRedirect(
      { branchName: "feature-1", branches: withoutFeature },
      confirmBranchList
    );
    await expect.poll(toastCount).toBe(1);
    await rerender({ branchName: null, branches: withoutFeature });

    // WHEN the same name comes back, e.g. the user hits back
    await rerender({ branchName: "feature-1", branches: withoutFeature });

    // THEN it redirects on the standing verdict rather than confirming again
    await expect.poll(toastCount).toBe(2);
    expect(confirmBranchList).toHaveBeenCalledOnce();
  });

  test("re-confirms a name the list carries again, whichever branch is selected", async () => {
    // GIVEN feature-1 was confirmed gone, then recreated while the user sat on another branch
    const confirmBranchList = vi
      .fn()
      .mockResolvedValueOnce(confirmsGone)
      .mockResolvedValue(confirmsBack);
    const { rerender } = await renderRedirect(
      { branchName: "feature-1", branches: withoutFeature },
      confirmBranchList
    );
    await expect.poll(toastCount).toBe(1);
    await rerender({ branchName: "feature-2", branches: withFeature });

    // WHEN the user lands on it while a fetched list transiently omits it again
    await rerender({ branchName: "feature-1", branches: withoutFeature });

    // THEN the miss is confirmed afresh instead of reusing the standing verdict
    await expect.poll(() => confirmBranchList.mock.calls.length).toBe(2);
    await settle();
    expect(toastCount()).toBe(1);
  });
});
