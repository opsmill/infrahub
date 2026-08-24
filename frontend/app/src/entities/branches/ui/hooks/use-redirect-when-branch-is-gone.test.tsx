import type React from "react";
import { MemoryRouter, useLocation } from "react-router";
import { toast } from "react-toastify";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

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

const listWithoutFeature: BranchListConfirmation = { data: [defaultBranch], isError: false };
const listWithFeature: BranchListConfirmation = {
  data: [defaultBranch, featureBranch],
  isError: false,
};
const failedFetch: BranchListConfirmation = { data: undefined, isError: true };

const STARTING_PAGE = "/objects/device";

type Props = { branchName: string | null; isMissingFromList: boolean };

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

describe("confirmsBranchIsGone", () => {
  test("confirms a branch the freshly fetched list does not contain", () => {
    expect(confirmsBranchIsGone(listWithoutFeature, "feature-1")).toBe(true);
  });

  test("clears a branch the freshly fetched list does contain", () => {
    expect(confirmsBranchIsGone(listWithFeature, "feature-1")).toBe(false);
  });

  test("confirms nothing when the fetch failed", () => {
    expect(confirmsBranchIsGone(failedFetch, "feature-1")).toBe(false);
  });

  test("never confirms an unnamed branch, which resolves to the default one", () => {
    expect(confirmsBranchIsGone(listWithoutFeature, null)).toBe(false);
  });
});

describe("useRedirectWhenBranchIsGone", () => {
  beforeEach(() => {
    vi.mocked(toast).mockClear();
  });

  test("redirects once a second fetch also misses the branch", async () => {
    // GIVEN
    const confirmBranchList = vi.fn().mockResolvedValue(listWithoutFeature);

    // WHEN
    const { result } = await renderRedirect(
      { branchName: "feature-1", isMissingFromList: true },
      confirmBranchList
    );

    // THEN
    await expect.poll(() => result.current).toBe("/");
    expect(toast).toHaveBeenCalledOnce();
  });

  test("stays put when the branch is back in the freshly fetched list", async () => {
    // GIVEN
    const confirmBranchList = vi.fn().mockResolvedValue(listWithFeature);

    // WHEN
    const { result } = await renderRedirect(
      { branchName: "feature-1", isMissingFromList: true },
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
      { branchName: "feature-1", isMissingFromList: true },
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
      { branchName: "feature-1", isMissingFromList: true },
      confirmBranchList
    );

    // THEN
    await expect.poll(() => confirmBranchList.mock.calls.length).toBe(1);
    await settle();
    expect(result.current).toBe(STARTING_PAGE);
  });

  test("does not confirm anything while the branch is in the list", async () => {
    // GIVEN
    const confirmBranchList = vi.fn().mockResolvedValue(listWithoutFeature);

    // WHEN
    const { result } = await renderRedirect(
      { branchName: "feature-1", isMissingFromList: false },
      confirmBranchList
    );

    // THEN
    await settle();
    expect(confirmBranchList).not.toHaveBeenCalled();
    expect(result.current).toBe(STARTING_PAGE);
  });

  test("does not apply a verdict to the branch the user moved on to", async () => {
    // GIVEN a confirmation for feature-1 held in flight
    let release: (() => void) | undefined;
    const confirmBranchList = vi.fn(
      () =>
        new Promise<BranchListConfirmation>((resolve) => {
          release = () => resolve(listWithoutFeature);
        })
    );
    const { result, rerender } = await renderRedirect(
      { branchName: "feature-1", isMissingFromList: true },
      confirmBranchList
    );
    await expect.poll(() => release !== undefined).toBe(true);

    // WHEN the user moves to a branch that resolves, and only then does the verdict land
    await rerender({ branchName: "feature-2", isMissingFromList: false });
    release?.();

    // THEN
    await settle();
    expect(result.current).toBe(STARTING_PAGE);
    expect(toast).not.toHaveBeenCalled();
  });

  test("redirects again on a revisit without asking the server twice", async () => {
    // GIVEN a branch already confirmed gone and redirected away from
    const confirmBranchList = vi.fn().mockResolvedValue(listWithoutFeature);
    const { rerender } = await renderRedirect(
      { branchName: "feature-1", isMissingFromList: true },
      confirmBranchList
    );
    await expect.poll(() => vi.mocked(toast).mock.calls.length).toBe(1);
    await rerender({ branchName: null, isMissingFromList: false });

    // WHEN the same name comes back, e.g. the user hits back
    await rerender({ branchName: "feature-1", isMissingFromList: true });

    // THEN it redirects on the standing verdict rather than confirming again
    await expect.poll(() => vi.mocked(toast).mock.calls.length).toBe(2);
    expect(confirmBranchList).toHaveBeenCalledOnce();
  });

  test("re-confirms a name used again rather than reusing the standing verdict", async () => {
    // GIVEN feature-1 was confirmed gone, then created again and seen in the list
    const confirmBranchList = vi
      .fn()
      .mockResolvedValueOnce(listWithoutFeature)
      .mockResolvedValue(listWithFeature);
    const { rerender } = await renderRedirect(
      { branchName: "feature-1", isMissingFromList: true },
      confirmBranchList
    );
    await expect.poll(() => vi.mocked(toast).mock.calls.length).toBe(1);
    await rerender({ branchName: "feature-1", isMissingFromList: false });

    // WHEN a later fetch transiently omits the live branch
    await rerender({ branchName: "feature-1", isMissingFromList: true });

    // THEN the miss is confirmed afresh and the branch is kept
    await expect.poll(() => confirmBranchList.mock.calls.length).toBe(2);
    await settle();
    expect(toast).toHaveBeenCalledOnce();
  });
});
