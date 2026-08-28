import type { ColumnDef } from "@tanstack/react-table";
import { describe, expect, it } from "vitest";

import type { NodeObject } from "@/entities/nodes/object/domain/model/node";

import {
  generateAttributeSchema,
  generateNodeSchema,
} from "../../../../../../../tests/fake/schema";
import { getObjectTableColumns } from "./get-object-table-columns";

// `columnHelper.accessor("name", …)` sets `accessorKey` and leaves `id` undefined; TanStack derives
// the column id from the accessor key when the table is built. Read both to get the resulting id.
const getColumnId = (column: ColumnDef<NodeObject>): string | undefined =>
  column.id ?? ("accessorKey" in column ? String(column.accessorKey) : undefined);

describe("getObjectTableColumns", () => {
  it("builds a column for a revealed extra attribute the default list-view rules exclude", () => {
    // GIVEN
    const extraAttribute = generateAttributeSchema({
      name: "internal_note",
      kind: "Text",
      label: "Internal Note",
      display: "extra",
    });
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({ name: "name", kind: "Text", label: "Name" }),
        extraAttribute,
      ],
      relationships: [],
    });

    // WHEN
    const defaultColumns = getObjectTableColumns(schema);
    const revealedColumns = getObjectTableColumns(schema, undefined, undefined, [extraAttribute]);

    // THEN
    expect(defaultColumns.map(getColumnId)).not.toContain("internal_note");
    expect(revealedColumns.map(getColumnId)).toContain("internal_note");
  });
});
