import { getFormFieldFromRelationship } from "@/shared/components/form/utils/getFormFieldFromRelationship";
import { buildRelationshipSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema.test";
import { describe, expect, it } from "vitest";
import { generateNodeSchema } from "../../../../../tests/fake/schema";

describe("getFormFieldFromRelationship", () => {
  const schema = generateNodeSchema();

  it("returns no fields that are read only", () => {
    // GIVEN
    const relationshipSchema = buildRelationshipSchema({ read_only: true });

    // WHEN
    const fields = getFormFieldFromRelationship({
      auth: undefined,
      relationshipSchema,
      relationshipData: undefined,
      objectTemplate: undefined,
      isFilterForm: false,
      schema,
    });

    // THEN
    expect(fields).toMatchObject({
      defaultValue: { source: null, value: null },
      description: "relationship many input for testing and development",
      disabled: true,
      label: "Tagone",
      name: "tagone",
      parent: undefined,
      relationship: relationshipSchema,
      rules: {
        required: false,
        validate: {
          required: expect.any(Function),
          maxCount: expect.any(Function),
          minCount: expect.any(Function),
        },
      },
      schema,
    });
  });
});
