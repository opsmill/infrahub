import { afterEach, describe, expect, test, vi } from "vitest";

import { useConfig } from "@/entities/config/ui/config-provider";
import { instanceBarClassName } from "@/entities/preferences/domain/rules/instance-color";

import { render } from "../../../../tests/components/render";
import { generateConfig } from "../../../../tests/fake/config";
import { InstanceColorBar } from "./instance-color-bar";

vi.mock("@/entities/config/ui/config-provider");

describe("InstanceColorBar", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  test("renders a bar carrying the class of the configured color", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(
      generateConfig({ instance: { label: null, color: "RED" } })
    );

    // WHEN
    const component = await render(<InstanceColorBar />);

    // THEN
    const bar = component.getByTestId("instance-color-bar");
    await expect.element(bar).toHaveClass(instanceBarClassName("RED"));
    await expect.element(bar).toHaveAttribute("aria-hidden", "true");
  });

  test("renders nothing when no color is set", async () => {
    // GIVEN
    vi.mocked(useConfig).mockReturnValue(
      generateConfig({ instance: { label: "QA", color: null } })
    );

    // WHEN
    const component = await render(<InstanceColorBar />);

    // THEN
    expect(component.getByTestId("instance-color-bar").query()).toBeNull();
  });
});
