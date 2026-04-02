import { Icon } from "@iconify-icon/react";

import { Col } from "@/shared/components/container";

import { AttributeFilterForm } from "@/entities/nodes/object/ui/filters/attribute-filter-form";
import { isMetadataDatetimeFilter } from "@/entities/nodes/object/ui/filters/metadata-filter-definitions";
import { RelationshipFilterForm } from "@/entities/nodes/object/ui/filters/relationship-filter-form";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

export interface MetadataFilterFormProps {
  metadataFilter: AttributeSchema | RelationshipSchema;
  onSuccess?: () => void;
}

export function MetadataFilterForm({ metadataFilter, onSuccess }: MetadataFilterFormProps) {
  return (
    <Col className="gap-0">
      <div className="flex items-center gap-1.5 border-gray-200 border-b px-3 py-2">
        <Icon icon="mdi:information-outline" className="text-gray-400 text-sm" />
        <span className="font-medium text-gray-500 text-xs uppercase tracking-wider">
          {metadataFilter.label}
        </span>
      </div>

      {isMetadataDatetimeFilter(metadataFilter) ? (
        <AttributeFilterForm attributeSchema={metadataFilter} onSuccess={onSuccess} />
      ) : (
        <RelationshipFilterForm relationshipSchema={metadataFilter} onSuccess={onSuccess} />
      )}
    </Col>
  );
}
