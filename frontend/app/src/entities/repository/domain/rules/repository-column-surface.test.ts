import { describe, expect, it } from "vitest";

import { FROM_RESOURCE_POOL_SUFFIX } from "@/shared/components/form/constants";

import { getColumnCandidates } from "@/entities/nodes/columns/domain/rules/get-column-candidates";
import { REPOSITORY_COLUMN_SURFACE } from "@/entities/repository/domain/rules/repository-column-surface";

import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../tests/fake/schema";

describe("REPOSITORY_COLUMN_SURFACE", () => {
  it("never lists the push state attributes, so a link cannot reveal them", () => {
    // GIVEN
    const schema = generateNodeSchema({
      kind: "CoreRepository",
      attributes: [
        generateAttributeSchema({ name: "name", kind: "Text" }),
        generateAttributeSchema({ name: "delivery_status", kind: "Dropdown", display: "extra" }),
        generateAttributeSchema({
          name: "delivery_last_delivered_commit",
          kind: "Text",
          display: "extra",
        }),
      ],
      relationships: [],
    });

    // WHEN
    const fields = getColumnCandidates(schema, REPOSITORY_COLUMN_SURFACE);

    // THEN
    expect(fields.map(({ name }) => name)).toEqual(["name"]);
  });

  it("still leaves out the fields the object surface leaves out", () => {
    // GIVEN
    const schema = generateNodeSchema({
      kind: "CoreRepository",
      attributes: [generateAttributeSchema({ name: "name", kind: "Text" })],
      relationships: [
        generateRelationshipSchema({
          name: `tags${FROM_RESOURCE_POOL_SUFFIX}`,
          kind: "Attribute",
          cardinality: "one",
        }),
      ],
    });

    // WHEN
    const fields = getColumnCandidates(schema, REPOSITORY_COLUMN_SURFACE);

    // THEN
    expect(fields.map(({ name }) => name)).toEqual(["name"]);
  });
});
