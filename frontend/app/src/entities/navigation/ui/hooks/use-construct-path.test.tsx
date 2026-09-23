import { Provider } from "jotai";
import type React from "react";
import { afterEach, describe, expect, test } from "vitest";
import { renderHook } from "vitest-browser-react";

import { generateBranch } from "@/../tests/fake/branch";

import { QSP } from "@/shared/config/qsp";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import { BranchContext } from "@/entities/branches/ui/branches-provider";
import { useConstructPath } from "@/entities/navigation/ui/hooks/use-construct-path";

// Deliberately not named "main": INFRAHUB_INITIAL_DEFAULT_BRANCH can rename the default branch.
const defaultBranch = generateBranch({ id: "branch-default", name: "primary", is_default: true });
const featureBranch = generateBranch({ id: "branch-feature", name: "feature-1" });

const renderConstructPath = (currentBranch: BranchListItem) =>
  renderHook(() => useConstructPath(), {
    wrapper: ({ children }: { children: React.ReactNode }) => (
      <Provider store={store}>
        <BranchContext value={{ currentBranch, setCurrentBranch: () => {} }}>
          {children}
        </BranchContext>
      </Provider>
    ),
  });

describe("useConstructPath", () => {
  afterEach(() => {
    store.set(datetimeAtom, null);
    window.history.replaceState(null, "", window.location.pathname);
  });

  test("omits the branch param on the default branch", async () => {
    // GIVEN
    const { result } = await renderConstructPath(defaultBranch);

    // WHEN
    const path = result.current("/");

    // THEN
    expect(path).toBe("/");
  });

  test("names the branch in the path when it is not the default branch", async () => {
    // GIVEN
    const { result } = await renderConstructPath(featureBranch);

    // WHEN
    const path = result.current("/");

    // THEN
    expect(path).toBe("/?branch=feature-1");
  });

  test("drops a branch inherited from the URL when the active branch is the default one", async () => {
    // GIVEN
    window.history.replaceState(null, "", `${window.location.pathname}?${QSP.BRANCH}=stale-branch`);
    const { result } = await renderConstructPath(defaultBranch);

    // WHEN
    const path = result.current("/");

    // THEN
    expect(path).toBe("/");
  });

  test("lets the caller target another branch than the active one", async () => {
    // GIVEN
    const { result } = await renderConstructPath(featureBranch);

    // WHEN
    const path = result.current("/tasks", [{ name: QSP.BRANCH, value: "other-branch" }]);

    // THEN
    expect(path).toBe("/tasks?branch=other-branch");
  });

  test("carries the time-machine date", async () => {
    // GIVEN
    store.set(datetimeAtom, new Date("2026-08-31T13:08:29.000Z"));
    const { result } = await renderConstructPath(featureBranch);

    // WHEN
    const path = result.current("/");

    // THEN
    expect(path).toBe("/?branch=feature-1&at=2026-08-31T13%3A08%3A29.000Z");
  });
});
