import { describe, expect, test } from "vitest";

import { render } from "../../../../../tests/components/render";
import { generateAttributeSchema, generateNodeSchema } from "../../../../../tests/fake/schema";
import { SortEditor } from "./sort-editor";

const schema = generateNodeSchema({
  order_by: ["name__value"],
  attributes: [
    generateAttributeSchema({ name: "name", label: "Name", kind: "Text" }),
    generateAttributeSchema({ name: "description", label: "Description", kind: "Text" }),
  ],
  relationships: [],
});

describe("SortEditor", () => {
  test("hides the schema default sort fields from the picker", async () => {
    // GIVEN
    const component = await render(<SortEditor schema={schema} />);

    // THEN
    await expect.element(component.getByRole("menuitem", { name: "Description" })).toBeVisible();
    await expect.element(component.getByRole("menuitem", { name: "Name" })).not.toBeInTheDocument();
  });
});
