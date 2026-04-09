import { AttributeFilterForm } from "@/entities/nodes/object/ui/filters/attribute-filter-form";
import { RelationshipFilterForm } from "@/entities/nodes/object/ui/filters/relationship-filter-form";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

interface FieldFilterFormProps {
  fieldSchema: AttributeSchema | RelationshipSchema;
  onSuccess?: () => void;
}

export function FieldFilterForm({ fieldSchema, onSuccess }: FieldFilterFormProps) {
  if ("peer" in fieldSchema) {
    return <RelationshipFilterForm relationshipSchema={fieldSchema} onSuccess={onSuccess} />;
  }

  return <AttributeFilterForm attributeSchema={fieldSchema} onSuccess={onSuccess} />;
}
