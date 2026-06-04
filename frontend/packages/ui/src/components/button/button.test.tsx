import { describe, expect, test } from "vitest";
import { render } from "vitest-browser-react";

import { Button } from "./button";

describe("Button (harness smoke test)", () => {
  test("renders an accessible button", async () => {
    // GIVEN a button with a label
    const component = await render(<Button>Click me</Button>);

    // THEN it is reachable by role + name
    await expect.element(component.getByRole("button", { name: "Click me" })).toBeVisible();
  });
});
