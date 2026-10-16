import React from "react";
import { afterEach, describe, expect, test } from "vitest";

import { render } from "@/../tests/components/render";
import { generateBranch } from "@/../tests/fake/branch";

import { SidebarProvider } from "@/shared/components/layout/sidebar";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import { BranchContext } from "@/entities/branches/ui/branches-provider";
import { AppSidebarHeader } from "@/entities/navigation/ui/sidebar/app-sidebar";

// Deliberately not named "main": INFRAHUB_INITIAL_DEFAULT_BRANCH can rename the default branch.
const defaultBranch = generateBranch({ id: "branch-default", name: "primary", is_default: true });
const featureBranch = generateBranch({ id: "branch-feature", name: "feature-1" });

// Switching branch only rewrites the query string, so the sidebar outlives it. The harness swaps
// the branch in place rather than remounting to reproduce that.
function SidebarHarness({ initialBranch }: { initialBranch: BranchListItem }) {
  const [currentBranch, setCurrentBranch] = React.useState(initialBranch);

  return (
    <BranchContext value={{ currentBranch, setCurrentBranch }}>
      <SidebarProvider>
        <AppSidebarHeader />
      </SidebarProvider>

      <button type="button" onClick={() => setCurrentBranch(featureBranch)}>
        Switch branch
      </button>
    </BranchContext>
  );
}

const getHomeHref = (container: HTMLElement) =>
  container.querySelector('a[aria-label="Infrahub home"]')?.getAttribute("href");

describe("AppSidebarHeader", () => {
  afterEach(() => {
    window.history.replaceState(null, "", window.location.pathname);
  });

  test("links home without a branch param on the default branch", async () => {
    // GIVEN
    const harness = <SidebarHarness initialBranch={defaultBranch} />;

    // WHEN
    const component = await render(harness);

    // THEN
    expect(getHomeHref(component.container)).toBe("/");
  });

  test("links home on the active branch", async () => {
    // GIVEN
    const harness = <SidebarHarness initialBranch={featureBranch} />;

    // WHEN
    const component = await render(harness);

    // THEN
    expect(getHomeHref(component.container)).toBe("/?branch=feature-1");
  });

  test("updates the home link when the branch changes after mount", async () => {
    // GIVEN
    const component = await render(<SidebarHarness initialBranch={defaultBranch} />);

    // WHEN
    await component.getByRole("button", { name: "Switch branch" }).click();

    // THEN
    await expect.poll(() => getHomeHref(component.container)).toBe("/?branch=feature-1");
  });
});
