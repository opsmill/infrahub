import { afterEach, describe, expect, test, vi } from "vitest";

import { useConfig } from "@/entities/config/ui/config-provider";

import { render } from "../../../../tests/components/render";
import { generateConfigWithInstance } from "../../../../tests/fake/config";
import { InstanceColorBar } from "./instance-color-bar";

vi.mock("@/entities/config/ui/config-provider");

describe("InstanceColorBar", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  test("renders a bar carrying the class of the configured color", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(generateConfigWithInstance(null, "RED"));

    // WHEN
    const component = await render(<InstanceColorBar />);

    // THEN
    const bar = component.getByTestId("instance-color-bar");
    await expect.element(bar).toHaveClass("bg-danger");
    await expect.element(bar).toHaveAttribute("aria-hidden", "true");
  });

  test("renders nothing when no color is set", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(generateConfigWithInstance("QA", null));

    // WHEN
    const component = await render(<InstanceColorBar />);

    // THEN
    expect(component.getByTestId("instance-color-bar").query()).toBeNull();
  });
});
