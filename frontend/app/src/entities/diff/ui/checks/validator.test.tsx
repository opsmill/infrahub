import { describe, expect, test } from "vitest";

import { render } from "../../../../../tests/components/render";
import { Validator } from "./validator";

const generateValidator = (conclusion: string) => ({
  id: "validator-1",
  __typename: "CoreArtifactValidator",
  display_label: "Artifact Validator: cabling_plan",
  started_at: { value: "2026-10-11T10:00:00Z" },
  completed_at: { value: "2026-10-11T10:05:00Z" },
  state: { value: "completed" },
  conclusion: { value: conclusion },
  definition: { node: null },
});

describe("Validator", () => {
  test("shows the skipped icon for a completed validator that skipped its checks", async () => {
    // GIVEN
    const component = await render(<Validator validator={generateValidator("skipped")} />);
    const icon = component.getByTestId("validator-skipped").element() as HTMLElement;

    // WHEN
    icon.focus();

    // THEN
    await expect.element(component.getByRole("tooltip", { name: "Skipped" })).toBeVisible();
  });

  test("keeps the success icon for a successful validator", async () => {
    // GIVEN
    const validator = generateValidator("success");

    // WHEN
    const component = await render(<Validator validator={validator} />);

    // THEN
    await expect.element(component.getByTestId("validator-success")).toBeInTheDocument();
    expect(component.getByTestId("validator-skipped").query()).toBeNull();
  });
});
