import { afterEach, describe, expect, test, vi } from "vitest";
import { page } from "vitest/browser";

import { useConfig } from "@/entities/config/ui/config-provider";

import { render } from "../../../../tests/components/render";
import { initPointerTracking } from "../../../../tests/components/utils";
import { generateConfigWithInstance } from "../../../../tests/fake/config";
import { InstanceBadge } from "./instance-badge";

vi.mock("@/entities/config/ui/config-provider");

const LONG_LABEL = "Production Europe West cluster 2";

describe("InstanceBadge", () => {
  afterEach(async () => {
    vi.resetAllMocks();
    // The pointer position persists across tests, so a tooltip left open by a hover would cover the next render.
    await initPointerTracking(page.elementLocator(document.body));
  });

  test("shows the label in the red variant when the color is RED", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(generateConfigWithInstance("QA", "RED"));

    // WHEN
    const component = await render(<InstanceBadge />);

    // THEN
    await expect.element(component.getByText("QA")).toBeVisible();
    await expect.element(component.getByText("QA")).toHaveClass("text-danger");
  });

  test("falls back to the gray variant when the label has no color", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(generateConfigWithInstance("QA", null));

    // WHEN
    const component = await render(<InstanceBadge />);

    // THEN
    await expect.element(component.getByText("QA")).toHaveClass("bg-content-strong");
  });

  test("renders nothing when no label is set", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(generateConfigWithInstance(null, "RED"));

    // WHEN
    const component = await render(<InstanceBadge />);

    // THEN
    expect(component.getByTestId("instance-badge").query()).toBeNull();
  });

  test("shows the full label in a tooltip on hover", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(generateConfigWithInstance(LONG_LABEL, "BLUE"));
    const component = await render(<InstanceBadge />);
    await initPointerTracking(component.locator);

    // WHEN
    await component.getByText(LONG_LABEL).hover();

    // THEN
    await expect.element(component.getByRole("tooltip", { name: LONG_LABEL })).toBeVisible();
  });
});
