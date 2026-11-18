import { describe, expect, test } from "vitest";

import { INFRAHUB_DOC_LOCAL } from "@/shared/config/config";

import { render } from "../../../../tests/components/render";
import { generateNodeSchema } from "../../../../tests/fake/schema";
import { SchemaHelpMenu } from "./schema-help-menu";

describe("SchemaHelpMenu", () => {
  test("links to an external documentation URL as-is", async () => {
    // GIVEN
    const schema = generateNodeSchema({ documentation: "https://wiki.example.com/x" });
    const component = await render(<SchemaHelpMenu schema={schema} />);

    // WHEN
    await component.getByTestId("schema-help-menu-trigger").click();

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: /Documentation/i }))
      .toHaveAttribute("href", "https://wiki.example.com/x");
  });

  test("links a relative documentation path to the bundled documentation", async () => {
    // GIVEN
    const schema = generateNodeSchema({ documentation: "/topics/object-template/" });
    const component = await render(<SchemaHelpMenu schema={schema} />);

    // WHEN
    await component.getByTestId("schema-help-menu-trigger").click();

    // THEN
    await expect
      .element(component.getByRole("menuitem", { name: /Documentation/i }))
      .toHaveAttribute("href", `${INFRAHUB_DOC_LOCAL}/topics/object-template/`);
  });
});
