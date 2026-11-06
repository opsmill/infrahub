import type { ColumnDef } from "@tanstack/react-table";
import React from "react";

import { CopyToClipboardButton } from "@/shared/components/buttons/copy-to-clipboard-button";
import { Col } from "@/shared/components/container";
import { DataTable } from "@/shared/components/table/data-table";
import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { TableCell } from "@/shared/components/table/table-cell";
import { Input } from "@/shared/components/ui/input";
import { classNames } from "@/shared/utils/common";
import { pluralize } from "@/shared/utils/string";

import type { ListElement } from "@/entities/nodes/object/domain/model/list-element";
import { filterListElements } from "@/entities/nodes/object/domain/rules/filter-list-elements";
import { isNodeReference } from "@/entities/nodes/object/domain/rules/is-node-reference";
import { JsonValueButton } from "@/entities/nodes/object/ui/attribute-values/json-value-button";
import { ListElementBadge } from "@/entities/nodes/object/ui/attribute-values/list-element-badge";
import { NodeKindCell } from "@/entities/nodes/object/ui/object-table/cells/node-kind-cell";

/** Up to this many elements are quicker to scan by scrolling than to filter. */
const LIST_UNFILTERED_MAX_ELEMENTS = 12;

const header = (label: string, className?: string) => () => (
  <div className={classNames(cellsStyle, cellHeaderStyle, className)}>{label}</div>
);

function ElementValue({
  element,
  attributeLabel,
}: {
  element: ListElement;
  attributeLabel: string;
}) {
  if (element.type === "Node") return <ListElementBadge element={element} />;

  if (element.type === "Object" || element.type === "Array") {
    return (
      <JsonValueButton
        value={element.value}
        attributeLabel={attributeLabel}
        subtitle={`element ${element.position}`}
        className="text-accent"
      />
    );
  }

  return (
    <span
      className={classNames("min-w-0 truncate", element.type !== "Text" && "font-mono text-xs")}
      title={element.text}
    >
      {element.text}
    </span>
  );
}

function ElementCopyButton({ element }: { element: ListElement }) {
  const node = isNodeReference(element.value) ? element.value : null;

  return (
    <CopyToClipboardButton
      data={node ? node.id : element.text}
      aria-label={node ? `Copy the ID of ${element.text}` : `Copy element ${element.position}`}
    />
  );
}

function getColumns(attributeLabel: string, hasTypeColumn: boolean): ColumnDef<ListElement>[] {
  return [
    {
      id: "position",
      header: header("#", "justify-end"),
      cell: ({ row }) => (
        <TableCell className="justify-end text-foreground-muted tabular-nums">
          {row.original.position}
        </TableCell>
      ),
    },
    {
      id: "value",
      header: header("Value"),
      cell: ({ row }) => (
        <TableCell>
          <ElementValue element={row.original} attributeLabel={attributeLabel} />
        </TableCell>
      ),
    },
    ...(hasTypeColumn
      ? [
          {
            id: "type",
            header: header("Type"),
            cell: ({ row }) => (
              <TableCell>
                {isNodeReference(row.original.value) ? (
                  <NodeKindCell kind={row.original.value.__typename} />
                ) : (
                  <span className="text-foreground-muted">{row.original.type}</span>
                )}
              </TableCell>
            ),
          } satisfies ColumnDef<ListElement>,
        ]
      : []),
    {
      id: "actions",
      header: header(""),
      cell: ({ row }) => (
        <TableCell className="justify-center p-0">
          <ElementCopyButton element={row.original} />
        </TableCell>
      ),
    },
  ];
}

export function ListElementsTable({
  elements,
  attributeLabel,
}: {
  elements: ListElement[];
  attributeLabel: string;
}) {
  const [query, setQuery] = React.useState("");
  const isFiltered = query.trim() !== "";
  const shownElements = filterListElements(elements, query);
  const hasTypeColumn = elements.some((element) => element.type !== "Text");

  return (
    <Col className="min-h-0">
      {elements.length > LIST_UNFILTERED_MAX_ELEMENTS && (
        <Input
          aria-label="Filter elements"
          placeholder={`Filter ${elements.length} elements`}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      )}

      {shownElements.length === 0 ? (
        <p className="px-1 py-2 text-foreground-muted text-sm">No element matches “{query}”</p>
      ) : (
        <div className="max-h-96 overflow-auto rounded-lg border bg-table-frame">
          <DataTable
            columns={getColumns(attributeLabel, hasTypeColumn)}
            data={shownElements}
            getRowId={(element) => String(element.position)}
            gridTemplateColumns={() =>
              hasTypeColumn
                ? "3.5rem minmax(0, 1fr) fit-content(14rem) 2.5rem"
                : "3.5rem minmax(0, 1fr) 2.5rem"
            }
          />
        </div>
      )}

      <p aria-live="polite" className="min-h-4 text-foreground-muted text-xs">
        {isFiltered && `${shownElements.length} of ${pluralize(elements.length, "element")}`}
      </p>
    </Col>
  );
}
