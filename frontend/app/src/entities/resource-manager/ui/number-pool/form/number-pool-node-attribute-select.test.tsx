import { describe, expect, test } from "vitest";

import { render } from "../../../../../../tests/components/render";
import { generateAttributeSchema, generateNodeSchema } from "../../../../../../tests/fake/schema";
import { NumberPoolNodeAttributeSelect } from "./number-pool-node-attribute-select";

describe("NumberPoolNodeAttributeSelect", () => {
  test("tells the user when the node has no editable number attribute", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      kind: "InfraSubinterface",
      label: "Subinterface",
      attributes: [
        generateAttributeSchema({ name: "name", label: "Name", kind: "Text" }),
        generateAttributeSchema({
          name: "computed_id",
          label: "Computed ID",
          kind: "Number",
          read_only: true,
        }),
      ],
    });
    const component = await render(
      <NumberPoolNodeAttributeSelect schema={schema} value={null} onChange={() => {}} />
    );

    // THEN
    const trigger = component.getByRole("button", { name: /Attribute/ });
    await expect.element(trigger).toBeDisabled();
    await expect.element(trigger).toHaveTextContent("No editable Number attribute");
  });
});
