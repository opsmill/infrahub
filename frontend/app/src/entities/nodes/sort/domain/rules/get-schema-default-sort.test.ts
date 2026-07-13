import { describe, expect, it } from "vitest";

import { getSchemaDefaultSort } from "@/entities/nodes/sort/domain/rules/get-schema-default-sort";

import { generateNodeSchema } from "../../../../../../tests/fake/schema";

describe("getSchemaDefaultSort", () => {
  it("maps `order_by` entries to ASC sorts when they carry no direction suffix", () => {
    // GIVEN
    const schema = generateNodeSchema({ order_by: ["name__value"] });

    // WHEN
    const defaultSort = getSchemaDefaultSort(schema);

    // THEN
    expect(defaultSort).toEqual([{ field: "name__value", direction: "ASC" }]);
  });

  it("honors `__asc`/`__desc` suffixes and preserves entry order", () => {
    // GIVEN
    const schema = generateNodeSchema({
      order_by: ["priority__value__desc", "name__value__asc", "site__name__value__desc"],
    });

    // WHEN
    const defaultSort = getSchemaDefaultSort(schema);

    // THEN
    expect(defaultSort).toEqual([
      { field: "priority__value", direction: "DESC" },
      { field: "name__value", direction: "ASC" },
      { field: "site__name__value", direction: "DESC" },
    ]);
  });

  it("returns null when the schema declares no `order_by`", () => {
    // GIVEN
    const nullOrderBy = generateNodeSchema({ order_by: null });
    const undefinedOrderBy = generateNodeSchema({ order_by: undefined });
    const emptyOrderBy = generateNodeSchema({ order_by: [] });

    // WHEN
    const fromNull = getSchemaDefaultSort(nullOrderBy);
    const fromUndefined = getSchemaDefaultSort(undefinedOrderBy);
    const fromEmpty = getSchemaDefaultSort(emptyOrderBy);

    // THEN
    expect(fromNull).toBeNull();
    expect(fromUndefined).toBeNull();
    expect(fromEmpty).toBeNull();
  });
});
