import type React from "react";

import { Row } from "@/shared/components/container";

import { RELATIONSHIP_COLUMN_SURFACE } from "@/entities/nodes/columns/domain/rules/column-surfaces";
import { ColumnsPicker } from "@/entities/nodes/columns/ui/columns-picker";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export interface RelationshipTableToolbarProps {
  schema: ModelSchema;
  actions?: React.ReactNode;
}

/**
 * The relationship tab's own toolbar row, hosting the column checklist and the host's actions.
 *
 * The schema arrives as a prop rather than from `useObjectTableContext()` because two of
 * `RelationshipTable`'s three hosts (`ipam-details-relationship-page.tsx`,
 * `repository-objects-manager.tsx`) render it without an `ObjectTableProvider`, so reading the
 * context here would throw. The surface is likewise named explicitly: the one host that does
 * provide a context (`object-relationships-manager.tsx`) carries the default object surface, whose
 * `canReveal: true` would offer `extra` fields the relationship fetch path never requests.
 */
export function RelationshipTableToolbar({ schema, actions }: RelationshipTableToolbarProps) {
  return (
    <Row className="p-2">
      <ColumnsPicker schema={schema} surface={RELATIONSHIP_COLUMN_SURFACE} />
      {actions && <Row className="ml-auto">{actions}</Row>}
    </Row>
  );
}
