import { AuthContextType } from "@/entities/authentication/ui/useAuth";
import { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { NodeObject } from "@/entities/nodes/types";
import { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";
import { ProfileData } from "@/shared/components/form/object-form";
import { DynamicFieldProps, NumberPoolData } from "@/shared/components/form/type";
import { FormContextType } from "@/shared/components/form/utils/form-context";
import { getFormFieldFromAttribute } from "@/shared/components/form/utils/getFormFieldFromAttribute";
import { getFormFieldFromRelationship } from "@/shared/components/form/utils/getFormFieldFromRelationship";
import { getRelationshipsForForm } from "@/shared/components/form/utils/getRelationshipsForForm";
import { sortByOrderWeight } from "@/shared/utils/common";

interface GetFormFieldsFromSchema extends FormContextType {
  schema: ModelSchema;
  profiles?: Array<ProfileData>;
  initialObject?: Record<string, AttributeType | RelationshipType>;
  objectTemplate?: NodeObject | null;
  auth?: AuthContextType;
  isFilterForm?: boolean;
  pools?: Array<NumberPoolData>;
  isUpdate?: boolean;
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
  parentSchema,
  parentData,
}: GetFormFieldsFromSchema): Array<DynamicFieldProps> => {
  const unorderedFields: Array<AttributeSchema | RelationshipSchema> = [
    ...(schema.attributes ?? []),
    ...getRelationshipsForForm(schema.relationships ?? [], isUpdate, schema),
  ].filter((attribute) => !attribute.read_only);
  const orderedFields: typeof unorderedFields = sortByOrderWeight(unorderedFields);

  return orderedFields.map((field) => {
    if ("peer" in field) {
      return getFormFieldFromRelationship({
        auth,
        relationshipSchema: field,
        relationshipData: initialObject?.[field.name] as RelationshipType | undefined,
        objectTemplate,
        isFilterForm: !!isFilterForm,
        schema,
        parentSchema,
        parentData,
      });
    }

    return getFormFieldFromAttribute({
      auth,
      attributeSchema: field,
      currentObject: initialObject as Record<string, AttributeType>,
      objectTemplate,
      isFilterForm: !!isFilterForm,
      schema,
      pools,
      profiles,
    });
  });
};
