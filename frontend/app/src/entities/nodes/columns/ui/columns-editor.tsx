import { Autocomplete, Button, Menu, MenuItem } from "@infrahub/ui";
import { ArrowUpDownIcon, CheckIcon, ListFilterIcon, RotateCcwIcon } from "lucide-react";

import { Col, Row } from "@/shared/components/container";

import type { ColumnSurface } from "@/entities/nodes/columns/domain/model/column-surface";
import { useColumnVisibility } from "@/entities/nodes/columns/ui/hooks/use-column-visibility";
import { isFieldFiltered } from "@/entities/nodes/filters/domain/rules/is-field-filtered";
import { useFilters } from "@/entities/nodes/filters/ui/hooks/use-filters";
import { findSortForField } from "@/entities/nodes/sort/domain/rules/find-sort-for-field";
import { useSort } from "@/entities/nodes/sort/ui/hooks/use-sort";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
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
  const { columnFields, columnVisibility, isCustomized, toggleColumn, reset } = useColumnVisibility(
    schema,
    surface
  );
  const { customSort } = useSort(schema);
  const [filters] = useFilters();

  return (
    <Col className="min-w-56">
      <Autocomplete>
        <Menu
          variant="picker"
          aria-label="Toggle columns"
          className="max-h-72"
          emptyMessage="No fields match"
        >
          {columnFields.map(({ name, label, fieldSchema, isDefaultVisible }) => {
            // The visibility state holds only the departures from the surface's defaults, so a
            // column neither param names is showing exactly when its surface shows it by default.
            const isVisible = name in columnVisibility ? columnVisibility[name] : isDefaultVisible;

            return (
              <MenuItem key={name} id={name} textValue={label} onAction={() => toggleColumn(name)}>
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

      {isCustomized && (
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
