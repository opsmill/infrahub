import {
  RELATIONSHIP_BULK_ADD_PREFIX,
  RELATIONSHIP_BULK_REMOVE_PREFIX,
} from "@/shared/components/form/constants";
import type { ProfileData } from "@/shared/components/form/object-form";
import type { DynamicFieldProps } from "@/shared/components/form/type";
import type { FormContextType } from "@/shared/components/form/utils/form-context";
import { getFormFieldFromAttribute } from "@/shared/components/form/utils/getFormFieldFromAttribute";
import { getFormFieldFromRelationship } from "@/shared/components/form/utils/getFormFieldFromRelationship";
import { getRelationshipsForForm } from "@/shared/components/form/utils/getRelationshipsForForm";
import { sortByOrderWeight } from "@/shared/utils/common";

import type { AuthContextType } from "@/entities/authentication/ui/useAuth";
import { isFileRelationship } from "@/entities/nodes/object/ui/object-details/object-data-display/utils/is-file-relationship";
import type { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import type { NodeObject } from "@/entities/nodes/types";
import type { NumberPool } from "@/entities/resource-manager/domain/type";
import type { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";

interface GetFormFieldsFromSchema extends FormContextType {
  schema: ModelSchema;
  profiles?: Array<ProfileData>;
  initialObject?: Record<string, AttributeType | RelationshipType>;
  objectTemplate?: NodeObject | null;
  auth?: AuthContextType;
  isFilterForm?: boolean;
  pools?: Array<NumberPool>;
  isUpdate?: boolean;
  isBulkUpdate?: boolean;
}

export const getFormFieldsFromSchema = ({
  schema,
  profiles,
  initialObject,
  objectTemplate,
  auth,
  isFilterForm,
  pools = [],
  isUpdate,
  isBulkUpdate,
  parentSchema,
  parentData,
}: GetFormFieldsFromSchema): Array<DynamicFieldProps> => {
  const unorderedFields: Array<AttributeSchema | RelationshipSchema> = [
    ...(schema.attributes ?? []).filter((attribute) => !isBulkUpdate || !attribute.unique),
    ...getRelationshipsForForm(schema.relationships ?? [], isUpdate || isBulkUpdate, schema),
  ].filter((attribute) => !attribute.read_only);
  const orderedFields = sortByOrderWeight(unorderedFields);

  return orderedFields.reduce((acc: Array<DynamicFieldProps>, field) => {
    if ("peer" in field) {
      // File relationships are handled separately via dedicated CoreFile form
      if (isFileRelationship(field)) {
        return acc;
      }

      if (isBulkUpdate && field.cardinality === "many") {
        return [
          ...acc,
          getFormFieldFromRelationship({
            type: "relationship-add",
            name: `${RELATIONSHIP_BULK_ADD_PREFIX}${field.name}`,
            auth,
            relationshipSchema: field,
            relationshipData: initialObject?.[field.name] as RelationshipType | undefined,
            objectTemplate,
            profiles,
            isFilterForm: !!isFilterForm,
            isBulkUpdate: !!isBulkUpdate,
            schema,
            parentSchema,
            parentData,
          }),
          getFormFieldFromRelationship({
            type: "relationship-remove",
            name: `${RELATIONSHIP_BULK_REMOVE_PREFIX}${field.name}`,
            auth,
            relationshipSchema: field,
            relationshipData: initialObject?.[field.name] as RelationshipType | undefined,
            objectTemplate,
            profiles,
            isFilterForm: !!isFilterForm,
            isBulkUpdate: !!isBulkUpdate,
            schema,
            parentSchema,
            parentData,
          }),
        ];
      }

      return [
        ...acc,
        getFormFieldFromRelationship({
          auth,
          relationshipSchema: field,
          relationshipData: initialObject?.[field.name] as RelationshipType | undefined,
          objectTemplate,
          profiles,
          isFilterForm: !!isFilterForm,
          isBulkUpdate: !!isBulkUpdate,
          schema,
          parentSchema,
          parentData,
        }),
      ];
    }

    return [
      ...acc,
      getFormFieldFromAttribute({
        auth,
        attributeSchema: field,
        currentObject: initialObject as Record<string, AttributeType>,
        objectTemplate,
        isFilterForm: !!isFilterForm,
        isBulkUpdate: !!isBulkUpdate,
        isUpdate: !!isUpdate,
        schema,
        pools,
        profiles,
      }),
    ];
  }, []);
};
