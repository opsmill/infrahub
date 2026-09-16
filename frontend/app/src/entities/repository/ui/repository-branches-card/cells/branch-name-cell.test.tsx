import { describe, expect, test } from "vitest";

import { BranchNameCell } from "@/entities/repository/ui/repository-branches-card/cells/branch-name-cell";

import { render } from "../../../../../../tests/components/render";

describe("BranchNameCell", () => {
  test("links the branch name to that branch's own detail page", async () => {
    // GIVEN
    const name = "feature/auth";

    // WHEN
    const component = await render(<BranchNameCell name={name} isDefault={false} />);

    // THEN
    await expect
      .element(component.getByRole("link", { name }))
      .toHaveAttribute("href", "/branches/feature%2Fauth");
  });

  test("marks the default branch", async () => {
    // WHEN
    const component = await render(<BranchNameCell name="main" isDefault />);

    // THEN
    await expect.element(component.getByText("default", { exact: true })).toBeVisible();
  });

  test("leaves a non-default branch unmarked", async () => {
    // WHEN
    const component = await render(<BranchNameCell name="staging" isDefault={false} />);

    // THEN
    expect(component.getByText("default", { exact: true }).elements()).toHaveLength(0);
  });

  test("renders no row-action control", async () => {
    // WHEN
    const component = await render(<BranchNameCell name="main" isDefault />);

    // THEN
    expect(component.getByRole("button").elements()).toHaveLength(0);
  });
});
