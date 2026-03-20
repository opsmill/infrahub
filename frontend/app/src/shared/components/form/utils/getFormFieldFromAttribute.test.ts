import { describe, expect, it } from "vitest";

import { FROM_RESOURCE_POOL_SUFFIX } from "@/shared/components/form/constants";

import { ATTRIBUTE_KIND } from "@/entities/schema/constants";

import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../tests/fake/schema";
import { getFormFieldFromAttribute } from "./getFormFieldFromAttribute";

describe("getFormFieldFromAttribute", () => {
  describe("number attribute with _from_resource_pool relationship", () => {
    it("attaches pool metadata with fromPoolRelationshipName when companion relationship exists", () => {
      const attributeSchema = generateAttributeSchema({
        name: "weight",
        kind: ATTRIBUTE_KIND.NUMBER,
      });

      const schema = generateNodeSchema({
        kind: "TestTemplate",
        attributes: [attributeSchema],
        relationships: [
          generateRelationshipSchema({
            name: `weight${FROM_RESOURCE_POOL_SUFFIX}`,
            peer: "CoreNumberPool",
            cardinality: "one",
            optional: true,
          }),
        ],
      });

      const field = getFormFieldFromAttribute({
        auth: undefined,
        attributeSchema,
        currentObject: undefined,
        objectTemplate: undefined,
        schema,
        isFilterForm: false,
        isUpdate: false,
        isBulkUpdate: false,
        pools: [],
      });

      expect(field.pool).toEqual({
        kind: "CoreNumberPool",
        defaultAllocatedObjectKind: "TestTemplate",
        fromPoolRelationshipName: "weight_from_resource_pool",
      });
    });

    it("does not attach pool metadata when no companion relationship exists", () => {
      const attributeSchema = generateAttributeSchema({
        name: "weight",
        kind: ATTRIBUTE_KIND.NUMBER,
      });

      const schema = generateNodeSchema({
        kind: "TestNode",
        attributes: [attributeSchema],
        relationships: [],
      });

      const field = getFormFieldFromAttribute({
        auth: undefined,
        attributeSchema,
        currentObject: undefined,
        objectTemplate: undefined,
        schema,
        isFilterForm: false,
        isUpdate: false,
        isBulkUpdate: false,
        pools: [],
      });

      expect(field.pool).toBeUndefined();
    });
  });
});
