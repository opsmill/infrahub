import { describe, expect, test } from "vitest";

import { render } from "../../../../tests/components/render";
import { generateBranch } from "../../../../tests/fake/branch";
import { BranchWorkingNotice } from "./branch-working-notice";

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

  test("switching replaces the warning with the working notice", async () => {
    // GIVEN
    const branch = generateBranch({ name: "platform-upgrade" });
    const component = await render(<BranchWorkingNotice branch={branch} />);

    // WHEN
    await component.getByTestId("switch-to-viewed-branch").click();

    // THEN
    await expect.element(component.getByTestId("branch-working-notice")).toBeVisible();
    expect(component.getByTestId("branch-mismatch-notice").query()).toBeNull();
  });

  test("does not move the content below it when switching", async () => {
    // GIVEN
    const branch = generateBranch({ name: "platform-upgrade" });
    const component = await render(
      <div className="w-[1000px]">
        <BranchWorkingNotice branch={branch} />
        <div data-testid="content-below">Branch details</div>
      </div>
    );
    const topBeforeSwitch = component
      .getByTestId("content-below")
      .element()
      .getBoundingClientRect().top;

    // WHEN
    await component.getByTestId("switch-to-viewed-branch").click();

    // THEN
    await expect.element(component.getByTestId("branch-working-notice")).toBeVisible();
    const topAfterSwitch = component
      .getByTestId("content-below")
      .element()
      .getBoundingClientRect().top;
    expect(topAfterSwitch).toBe(topBeforeSwitch);
  });
});
