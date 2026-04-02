import { Icon } from "@iconify-icon/react";

import { Col, Row } from "@/shared/components/container";

import { isMetadataDatetimeFilter } from "@/entities/nodes/object/domain/metadata-filter-definitions";
import { AttributeFilterForm } from "@/entities/nodes/object/ui/filters/attribute-filter-form";
import { RelationshipFilterForm } from "@/entities/nodes/object/ui/filters/relationship-filter-form";
import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

export interface MetadataFilterFormProps {
  metadataFilter: AttributeSchema | RelationshipSchema;
  onSuccess?: () => void;
}

export function MetadataFilterForm({ metadataFilter, onSuccess }: MetadataFilterFormProps) {
  return (
    <Col className="gap-0">
      <Row className="gap-1.5 border-gray-200 border-b px-3 py-2">
        <Icon icon="mdi:information-outline" className="text-gray-400 text-sm" />
        <span className="font-medium text-gray-500 text-xs uppercase tracking-wider">
          {metadataFilter.label}
        </span>
      </Row>

      {isMetadataDatetimeFilter(metadataFilter) ? (
        <AttributeFilterForm attributeSchema={metadataFilter} onSuccess={onSuccess} />
      ) : (
        <RelationshipFilterForm relationshipSchema={metadataFilter} onSuccess={onSuccess} />
      )}
    </Col>
  );
}
