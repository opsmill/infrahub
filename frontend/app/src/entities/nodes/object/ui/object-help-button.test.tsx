import { describe, expect, test } from "vitest";

import { INFRAHUB_DOC_LOCAL } from "@/shared/config/config";

import { render } from "../../../../../tests/components/render";
import { ObjectHelpButton } from "./object-help-button";

describe("ObjectHelpButton", () => {
  test("links to an external documentation URL as-is", async () => {
    // GIVEN
    const component = await render(
      <ObjectHelpButton documentationUrl="https://wiki.example.com/x" kind="TestNode" />
    );

    // WHEN
    await component.getByRole("button", { name: "?" }).click();

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: /Documentation/i }))
      .toHaveAttribute("href", "https://wiki.example.com/x");
  });

  test("links a relative documentation path to the bundled documentation", async () => {
    // GIVEN
    const component = await render(
      <ObjectHelpButton documentationUrl="/topics/object-template/" kind="TestNode" />
    );

    // WHEN
    await component.getByRole("button", { name: "?" }).click();

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: /Documentation/i }))
      .toHaveAttribute("href", `${INFRAHUB_DOC_LOCAL}/topics/object-template/`);
  });
});
