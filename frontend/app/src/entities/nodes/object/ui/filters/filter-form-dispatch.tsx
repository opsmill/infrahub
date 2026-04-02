import { isMetadataFilter } from "@/entities/nodes/object/domain/metadata-filter-definitions";
import { AttributeFilterForm } from "@/entities/nodes/object/ui/filters/attribute-filter-form";
import { MetadataFilterForm } from "@/entities/nodes/object/ui/filters/metadata-filter-form";
import { RelationshipFilterForm } from "@/entities/nodes/object/ui/filters/relationship-filter-form";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

interface FilterFormDispatchProps {
  fieldSchema: AttributeSchema | RelationshipSchema;
  onSuccess?: () => void;
}

export function FilterFormDispatch({ fieldSchema, onSuccess }: FilterFormDispatchProps) {
  if (isMetadataFilter(fieldSchema.name)) {
    return <MetadataFilterForm metadataFilter={fieldSchema} onSuccess={onSuccess} />;
  }

  if ("peer" in fieldSchema) {
    return <RelationshipFilterForm relationshipSchema={fieldSchema} onSuccess={onSuccess} />;
  }

  return <AttributeFilterForm attributeSchema={fieldSchema} onSuccess={onSuccess} />;
}
