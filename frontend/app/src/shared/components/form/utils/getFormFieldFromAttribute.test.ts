import { describe, expect, it } from "vitest";

import { FROM_RESOURCE_POOL_SUFFIX } from "@/shared/components/form/constants";

import { ATTRIBUTE_KIND } from "@/entities/schema/domain/model/attribute-kind";

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
        isDefaultBranch: undefined,
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
        options: [],
      });
    });

    it("attaches pool metadata from the pre-fetched pools alone, with no companion relationship", () => {
      // A plain node never grows `<name>_from_resource_pool` — only its template does — so the
      // existence of a number pool for this attribute is the only evidence the field can offer
      // one. It still has to land on `pool`, or the value-or-pool tabs would never appear.
      const attributeSchema = generateAttributeSchema({
        name: "weight",
        kind: ATTRIBUTE_KIND.NUMBER,
      });

      const schema = generateNodeSchema({
        kind: "TestNode",
        attributes: [attributeSchema],
        relationships: [],
      });

      const numberPool = {
        id: "number-pool-1",
        display_label: "Weights pool",
        __typename: "CoreNumberPool",
        schemaKind: "TestNode",
        attributeName: "weight",
      };

      const field = getFormFieldFromAttribute({
        auth: undefined,
        isDefaultBranch: undefined,
        attributeSchema,
        currentObject: undefined,
        objectTemplate: undefined,
        schema,
        isFilterForm: false,
        isUpdate: false,
        isBulkUpdate: false,
        pools: [numberPool],
      });

      expect(field.pool).toEqual({
        kind: "CoreNumberPool",
        defaultAllocatedObjectKind: "TestNode",
        // No relationship, so a pool value is submitted on the field itself — exactly as before.
        fromPoolRelationshipName: undefined,
        options: [numberPool],
      });
    });

    it("offers only the pools configured for this attribute", () => {
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
        isDefaultBranch: undefined,
        attributeSchema,
        currentObject: undefined,
        objectTemplate: undefined,
        schema,
        isFilterForm: false,
        isUpdate: false,
        isBulkUpdate: false,
        pools: [
          {
            id: "other-pool",
            display_label: "Heights pool",
            __typename: "CoreNumberPool",
            schemaKind: "TestNode",
            attributeName: "height",
          },
        ],
      });

      // A pool for a sibling attribute is no pool for this field, so nothing is offered.
      expect(field.pool).toBeUndefined();
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
        isDefaultBranch: undefined,
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
