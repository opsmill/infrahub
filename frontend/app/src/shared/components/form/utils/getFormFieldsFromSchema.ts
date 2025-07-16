import { AuthContextType } from "@/entities/authentication/ui/useAuth";
import { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { NodeObject } from "@/entities/nodes/types";
import { NumberPool } from "@/entities/resource-manager/domain/type";
import { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";
import { ProfileData } from "@/shared/components/form/object-form";
import { DynamicFieldProps } from "@/shared/components/form/type";
import { getFormFieldFromAttribute } from "@/shared/components/form/utils/getFormFieldFromAttribute";
import { getFormFieldFromRelationship } from "@/shared/components/form/utils/getFormFieldFromRelationship";
import { getRelationshipsForForm } from "@/shared/components/form/utils/getRelationshipsForForm";
import { sortByOrderWeight } from "@/shared/utils/common";

type GetFormFieldsFromSchema = {
  schema: ModelSchema;
  profiles?: Array<ProfileData>;
  initialObject?: Record<string, AttributeType | RelationshipType>;
  objectTemplate?: NodeObject | null;
  auth?: AuthContextType;
  isFilterForm?: boolean;
  pools?: Array<NumberPool>;
  isUpdate?: boolean;
};

export const getFormFieldsFromSchema = ({
  schema,
  profiles,
  initialObject,
  objectTemplate,
  auth,
  isFilterForm,
  pools = [],
  isUpdate,
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
