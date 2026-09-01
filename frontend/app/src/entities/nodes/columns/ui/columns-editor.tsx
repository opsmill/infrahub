import { Autocomplete, Button, Menu, MenuItem } from "@infrahub/ui";
import { useAtomValue } from "jotai";
import { ArrowUpDownIcon, CheckIcon, ListFilterIcon, RotateCcwIcon } from "lucide-react";

import { Col, Row } from "@/shared/components/container";

import type { ColumnSurface } from "@/entities/nodes/columns/domain/model/column-surface";
import type { ColumnField } from "@/entities/nodes/columns/domain/rules/get-column-fields";
import { useColumnVisibility } from "@/entities/nodes/columns/ui/hooks/use-column-visibility";
import { isFieldFiltered } from "@/entities/nodes/filters/domain/rules/is-field-filtered";
import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";
import { findSortForField } from "@/entities/nodes/sort/domain/rules/find-sort-for-field";
import { useSort } from "@/entities/nodes/sort/ui/hooks/use-sort";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { getRelationshipLabel } from "@/entities/schema/domain/rules/get-relationship-label";
import { isRelationshipSchema } from "@/entities/schema/domain/rules/is-relationship-schema";
import { resolveSchema } from "@/entities/schema/domain/rules/resolve-schema";
import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
  templateSchemasAtom,
} from "@/entities/schema/stores/schema.atom";
import { FieldSchemaIcon } from "@/entities/schema/ui/field-schema-icon";

interface ColumnsEditorProps {
  schema: ModelSchema;
  surface?: ColumnSurface;
}

/**
 * The searchable column checklist: one item per column the surface can show, ticked when the column
 * is on screen right now.
 *
 * A column carrying an active sort or filter is flagged rather than locked, so hiding it stays
 * possible — the sort and the filter still apply to the rows, they are just no longer on display.
 */
export function ColumnsEditor({ schema, surface }: ColumnsEditorProps) {
  const { columnFields, columnVisibility, hasColumnParamsInUrl, toggleColumn, reset } =
    useColumnVisibility(schema, surface);
  const { customSort } = useSort(schema);
  const [filters] = useFilters();

  const nodeSchemas = useAtomValue(nodeSchemasAtom);
  const genericSchemas = useAtomValue(genericSchemasAtom);
  const profileSchemas = useAtomValue(profileSchemasAtom);
  const templateSchemas = useAtomValue(templateSchemasAtom);

  /**
   * The very string the table header shows for this column.
   *
   * `getRelationshipLabel` prefers the peer's own label for a hierarchical relationship, so the
   * picker and the header would otherwise disagree about the same column. Resolving the peer needs
   * the loaded schemas, which is a `ui/` concern — `getColumnFields` stays pure and keeps returning
   * the schema-declared label as the fallback used everywhere else.
   */
  const getHeaderLabel = ({ label, fieldSchema }: ColumnField) => {
    if (!isRelationshipSchema(fieldSchema)) return label;

    const { schema: peerSchema } = resolveSchema(fieldSchema.peer, {
      nodeSchemas,
      genericSchemas,
      profileSchemas,
      templateSchemas,
    });

    return getRelationshipLabel(fieldSchema, peerSchema);
  };

  // The visibility state holds only the departures from the surface's defaults, so a column neither
  // param names is showing exactly when its surface shows it by default.
  const isColumnVisible = ({ name, isDefaultVisible }: ColumnField) =>
    name in columnVisibility ? columnVisibility[name] : isDefaultVisible;
  // `getColumnVisibilityState` refuses to hide the last field column, so unchecking it would write a
  // param the trust boundary immediately relaxes — a click with nothing to show for it. Greying the
  // item out says why instead of letting the user hunt for the reason.
  const visibleColumnCount = columnFields.filter(isColumnVisible).length;

  return (
    <Col className="min-w-56">
      <Autocomplete>
        <Menu
          variant="picker"
          aria-label="Toggle columns"
          className="max-h-72"
          emptyMessage="No fields match"
        >
          {columnFields.map((columnField) => {
            const { name, fieldSchema } = columnField;
            const label = getHeaderLabel(columnField);
            const isVisible = isColumnVisible(columnField);
            const isLastVisible = isVisible && visibleColumnCount === 1;

            return (
              <MenuItem
                key={name}
                id={name}
                textValue={label}
                isDisabled={isLastVisible}
                tooltip={isLastVisible ? "At least one column must stay visible" : undefined}
                onAction={() => toggleColumn(name)}
              >
                <FieldSchemaIcon fieldSchema={fieldSchema} />
                <span>{label}</span>

                <Row className="ml-auto gap-1 text-stone-400">
                  {findSortForField(customSort, fieldSchema) && (
                    <>
                      <ArrowUpDownIcon />
                      <span className="sr-only">active sort</span>
                    </>
                  )}

                  {filters.some((filter) => isFieldFiltered(filter, name)) && (
                    <>
                      <ListFilterIcon />
                      <span className="sr-only">active filter</span>
                    </>
                  )}

                  {isVisible && (
                    <>
                      <CheckIcon className="text-cyan-600" />
                      <span className="sr-only">visible</span>
                    </>
                  )}
                </Row>
              </MenuItem>
            );
          })}
        </Menu>
      </Autocomplete>

      {hasColumnParamsInUrl && (
        <Row className="border-stone-300 border-t p-1">
          <Button variant="ghost" size="xxs" className="text-stone-500" onPress={reset}>
            <RotateCcwIcon />
            Reset columns
          </Button>
        </Row>
      )}
    </Col>
  );
}
