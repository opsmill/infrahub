import { describe, expect, it } from "vitest";

import { getFormFieldFromRelationship } from "@/shared/components/form/utils/getFormFieldFromRelationship";

import { generateNodeSchema, generateRelationshipSchema } from "../../../../../tests/fake/schema";
import { DEFAULT_FORM_FIELD_VALUE } from "../constants";

describe("getFormFieldFromRelationship", () => {
  const schema = generateNodeSchema();

  it("returns no fields that are read only", () => {
    // GIVEN
    const relationshipSchema = generateRelationshipSchema({ read_only: true });

    // WHEN
    const fields = getFormFieldFromRelationship({
      auth: undefined,
      relationshipSchema,
      relationshipData: undefined,
      objectTemplate: undefined,
      isFilterForm: false,
      schema,
      isBulkUpdate: false,
    });

    // THEN
    expect(fields).toMatchObject({
      defaultValue: DEFAULT_FORM_FIELD_VALUE,
      description: undefined,
      disabled: true,
      label: "Relationship test",
      name: "test_relationship",
      parent: undefined,
      relationship: relationshipSchema,
      rules: {
        required: false,
        validate: expect.any(Function),
      },
      schema,
    });
  });
});
