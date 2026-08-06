import { describe, expect, test, vi } from "vitest";

import { render } from "../../../../tests/components/render";
import { generateBranch } from "../../../../tests/fake/branch";
import { BranchWorkingNotice } from "./branch-working-notice";
import { BranchContext } from "./branches-provider";

// The render helper seeds the branch context with generateBranch(), so a branch
// named "test-branch" is the one being worked on.
const WORKING_BRANCH_NAME = "test-branch";

describe("BranchWorkingNotice", () => {
  test("states that you are working on the branch you are viewing", async () => {
    // GIVEN
    const branch = generateBranch({ name: WORKING_BRANCH_NAME });

    // WHEN
    const component = await render(<BranchWorkingNotice branch={branch} />);

    // THEN
    await expect.element(component.getByText("You're working on this branch.")).toBeVisible();
    expect(component.getByTestId("switch-to-viewed-branch").query()).toBeNull();
  });

  test("warns and offers a switch when the viewed branch is not the one being worked on", async () => {
    // GIVEN
    const branch = generateBranch({ name: "platform-upgrade" });

    // WHEN
    const component = await render(<BranchWorkingNotice branch={branch} />);

    // THEN
    await expect.element(component.getByTestId("branch-mismatch-notice")).toBeVisible();
    await expect
      .element(
        component.getByText(
          `You're viewing platform-upgrade but working on ${WORKING_BRANCH_NAME}.`
        )
      )
      .toBeVisible();
    await expect.element(component.getByTestId("switch-to-viewed-branch")).toBeVisible();
  });

  test("asks to work on the viewed branch when the switch is pressed", async () => {
    // GIVEN
    const branch = generateBranch({ name: "platform-upgrade" });
    const setCurrentBranch = vi.fn();
    const component = await render(
      <BranchContext value={{ currentBranch: generateBranch(), setCurrentBranch }}>
        <BranchWorkingNotice branch={branch} />
      </BranchContext>
    );

    // WHEN
    await component.getByTestId("switch-to-viewed-branch").click();

    // THEN
    expect(setCurrentBranch).toHaveBeenCalledWith(branch);
  });
});
