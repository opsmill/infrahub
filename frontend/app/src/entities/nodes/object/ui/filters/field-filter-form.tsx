import type { FilterDefinition } from "@/entities/nodes/object/domain/filter-definition";
import { AttributeFilterForm } from "@/entities/nodes/object/ui/filters/attribute-filter-form";
import { DateMetadataFilterForm } from "@/entities/nodes/object/ui/filters/date-metadata-filter-form";
import { UserMetadataFilterForm } from "@/entities/nodes/object/ui/filters/user-metadata-filter-form";
import { RelationshipFilterForm } from "@/entities/nodes/object/ui/filters/relationship-filter-form";

interface FieldFilterFormProps {
  definition: FilterDefinition;
  onSuccess: () => void;
}

export function FieldFilterForm({ definition, onSuccess }: FieldFilterFormProps) {
  switch (definition.type) {
    case "attribute":
      return <AttributeFilterForm attributeSchema={definition.schema} onSuccess={onSuccess} />;
    case "relationship":
      return (
        <RelationshipFilterForm relationshipSchema={definition.schema} onSuccess={onSuccess} />
      );
    case "metadata-date":
      return <DateMetadataFilterForm definition={definition} onSuccess={onSuccess} />;
    case "metadata-user":
      return <UserMetadataFilterForm definition={definition} onSuccess={onSuccess} />;
  }
}
