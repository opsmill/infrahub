import { describe, expect, it } from "vitest";

import type { components } from "@/shared/api/rest/types.generated";
import { FROM_RESOURCE_POOL_SUFFIX } from "@/shared/components/form/constants";

import { ATTRIBUTE_KIND } from "@/entities/schema/domain/model/attribute-kind";
import type { AttributeSchema } from "@/entities/schema/domain/model/schema";

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

  describe("IPHost attribute", () => {
    type IPHostAttributeParameters = components["schemas"]["IPHostAttributeParametersRead"];

    const buildIpHostField = (parameters: IPHostAttributeParameters | null) => {
      const attributeSchema = generateAttributeSchema({
        name: "management_address",
        kind: ATTRIBUTE_KIND.IP_HOST,
        label: "Management Address",
        parameters: parameters as AttributeSchema["parameters"],
      });

      return getFormFieldFromAttribute({
        auth: undefined,
        attributeSchema,
        currentObject: undefined,
        objectTemplate: undefined,
        schema: generateNodeSchema({ kind: "TestDevice", attributes: [attributeSchema] }),
        isFilterForm: false,
        isUpdate: false,
        isBulkUpdate: false,
      });
    };

    const plainTextField = (() => {
      const attributeSchema = generateAttributeSchema({
        name: "management_address",
        kind: ATTRIBUTE_KIND.TEXT,
        label: "Management Address",
        parameters: null,
      });

      return getFormFieldFromAttribute({
        auth: undefined,
        attributeSchema,
        currentObject: undefined,
        objectTemplate: undefined,
        schema: generateNodeSchema({ kind: "TestDevice", attributes: [attributeSchema] }),
        isFilterForm: false,
        isUpdate: false,
        isBulkUpdate: false,
      });
    })();

    // An address that carries no subnet prefix is edited through the same single free-text input as
    // one that does: the address form never offers a way to enter a prefix length. Both parameter
    // shapes are pinned so that adding a dedicated address input cannot introduce a prefix control
    // for either of them unnoticed.
    it.each([
      ["no parameters", null],
      ["a prefix-carrying declaration", { allow_prefix: true }],
      ["a bare-address declaration", { allow_prefix: false }],
    ] as const)("offers a single free-text input given %s", (_description, parameters) => {
      const field = buildIpHostField(parameters);

      expect(field.type).toBe(ATTRIBUTE_KIND.IP_HOST);
      expect(Object.keys(field).filter((key) => /prefix/i.test(key))).toEqual([]);
      expect(field.pool).toBeUndefined();
      expect(Object.keys(field).sort()).toEqual(Object.keys(plainTextField).sort());
    });
  });
});
