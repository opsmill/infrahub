import { AuthContextType } from "@/entities/authentication/ui/useAuth";
import { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import { ProfileData } from "@/shared/components/form/object-form";
import { DynamicFieldProps, NumberPoolData } from "@/shared/components/form/type";
import { getFormFieldFromAttribute } from "@/shared/components/form/utils/getFormFieldFromAttribute";
import { getFormFieldFromRelationship } from "@/shared/components/form/utils/getFormFieldFromRelationship";
import { getRelationshipsForForm } from "@/shared/components/form/utils/getRelationshipsForForm";
import { sortByOrderWeight } from "@/shared/utils/common";

type GetFormFieldsFromSchema = {
  schema: IModelSchema;
  profiles?: Array<ProfileData>;
  initialObject?: Record<string, AttributeType | RelationshipType>;
  auth?: AuthContextType;
  isFilterForm?: boolean;
  pools?: Array<NumberPoolData>;
  isUpdate?: boolean;
};

export const getFormFieldsFromSchema = ({
  schema,
  profiles,
  initialObject,
  auth,
  isFilterForm,
  pools = [],
  isUpdate,
}: GetFormFieldsFromSchema): Array<DynamicFieldProps> => {
  const unorderedFields = [
    ...(schema.attributes ?? []),
    ...getRelationshipsForForm(schema.relationships ?? [], isUpdate),
  ].filter((attribute) => !attribute.read_only);
  const orderedFields: typeof unorderedFields = sortByOrderWeight(unorderedFields);

  return orderedFields.map((attribute) => {
    if ("peer" in attribute) {
      return getFormFieldFromRelationship({
        auth,
        relationshipSchema: attribute,
        relationshipData: initialObject?.[attribute.name] as RelationshipType | undefined,
        isFilterForm: !!isFilterForm,
        schema,
      });
    }

    return getFormFieldFromAttribute({
      auth,
      attributeSchema: attribute,
      currentObject: initialObject as Record<string, AttributeType>,
      isFilterForm: !!isFilterForm,
      schema,
      pools,
      profiles,
    });
  });
};
