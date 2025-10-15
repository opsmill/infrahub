import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import type { DynamicFieldProps } from "@/shared/components/form/type";

import type { ConvertFieldMapping, ConvertFormFieldValue } from "@/entities/nodes/convert/types";
import { hasFieldMapping } from "@/entities/nodes/convert/utils/has-field-mapping";
import type { Node } from "@/entities/nodes/getObjectItemDisplayValue";
import type {
  NodeAttribute,
  NodeObject,
  NodeRelationshipMany,
  NodeRelationshipOne,
} from "@/entities/nodes/types";

export interface getFieldValueFromMappingParams {
  conversionMapping: ConvertFieldMapping | undefined;
  sourceObject: NodeObject;
  field: DynamicFieldProps;
}

export function getFieldValueFromMapping({
  conversionMapping,
  sourceObject,
  field,
}: getFieldValueFromMappingParams): ConvertFormFieldValue {
  const hasMapping = hasFieldMapping(conversionMapping);
  const fieldData = sourceObject[field.name];

  if (!hasMapping) return DEFAULT_FORM_FIELD_VALUE;

  if (field.type === "relationship") {
    if (field.relationship.cardinality === "many") {
      const nodes = (fieldData as NodeRelationshipMany | undefined)?.edges
        .map(({ node }) => node)
        .filter((node) => !!node);

      return {
        source: {
          type: "source",
          name: field.name,
        },
        value: (nodes as Array<Node>) ?? null,
      };
    } else {
      return {
        source: {
          type: "source",
          name: field.name,
        },
        value: ((fieldData as NodeRelationshipOne | undefined)?.node as Node | null) ?? null,
      };
    }
  }

  return {
    source: {
      type: "source",
      name: field.name,
    },
    value: (fieldData as NodeAttribute | undefined)?.value ?? null,
  };
}
