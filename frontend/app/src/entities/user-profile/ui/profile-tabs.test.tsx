import { describe, expect, test } from "vitest";

import { render } from "../../../../tests/components/render";
import { ProfileTabs } from "./profile-tabs";

describe("ProfileTabs", () => {
  test("renders the core profile tabs", async () => {
    const component = await render(<ProfileTabs />);

    await expect.element(component.getByRole("link", { name: "Profile" })).toBeVisible();
    await expect.element(component.getByRole("link", { name: "Tokens" })).toBeVisible();
    await expect.element(component.getByRole("link", { name: "Password" })).toBeVisible();
    expect(component.getByRole("link", { name: "Global preferences" }).elements()).toHaveLength(0);
  });
});
