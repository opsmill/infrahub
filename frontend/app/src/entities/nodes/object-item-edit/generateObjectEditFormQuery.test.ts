import { describe, expect, it } from "vitest";

import { generateObjectEditFormQuery } from "@/entities/nodes/object-item-edit/generateObjectEditFormQuery";
import type { NodeSchema } from "@/entities/schema/types";

import { generateGenericSchema, generateNodeSchema } from "../../../../tests/fake/schema";

describe("generateObjectEditFormQuery", () => {
  it("requests the profiles field for a node schema with generate_profile enabled", () => {
    // GIVEN
    const schema = generateNodeSchema({ generate_profile: true });

    // WHEN
    const query = generateObjectEditFormQuery({ schema, objectId: "object-id" });

    // THEN
    expect(query).toContain("profiles");
  });

  it("does not request the profiles field for a generic schema even with generate_profile enabled", () => {
    // GIVEN a generic schema, which inherits generate_profile:true but has no profiles relationship
    const schema = generateGenericSchema({ generate_profile: true }) as unknown as NodeSchema;

    // WHEN
    const query = generateObjectEditFormQuery({ schema, objectId: "object-id" });

    // THEN
    expect(query).not.toContain("profiles");
  });
});
