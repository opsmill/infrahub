import { describe, expect, it } from "vitest";

import { generateRackElevationKinds } from "../../../../../tests/fake/rack-elevation";
import { generateAttributeSchema, generateNodeSchema } from "../../../../../tests/fake/schema";
import { getMountableAttributeOptions } from "./get-mountable-attribute-options";

describe("getMountableAttributeOptions", () => {
  it("lists the attributes of mountable kinds and their Dropdown attributes for colors", () => {
    // GIVEN
    const device = generateNodeSchema({
      kind: "DcimDevice",
      attributes: [
        generateAttributeSchema({ name: "name", label: "Name", kind: "Text" }),
        generateAttributeSchema({ name: "role", label: "Role", kind: "Dropdown" }),
      ],
    });
    const rack = generateNodeSchema({
      kind: "LocationRack",
      attributes: [generateAttributeSchema({ name: "height", label: "Height", kind: "Number" })],
    });

    // WHEN
    const options = getMountableAttributeOptions({
      kinds: generateRackElevationKinds(),
      schemas: [device, rack],
    });

    // THEN
    expect(options.labelBy).toEqual([
      { name: "name", label: "Name" },
      { name: "role", label: "Role" },
    ]);
    expect(options.colorBy).toEqual([{ name: "role", label: "Role" }]);
  });
});
