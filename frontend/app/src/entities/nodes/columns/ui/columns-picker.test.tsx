import { beforeEach, describe, expect, test } from "vitest";

import { render } from "../../../../../tests/components/render";
import { generateAttributeSchema, generateNodeSchema } from "../../../../../tests/fake/schema";
import { ColumnsPicker } from "./columns-picker";

const objectSchema = generateNodeSchema({
  attributes: [
    generateAttributeSchema({ name: "name", label: "Name", kind: "Text", order_weight: 1000 }),
    generateAttributeSchema({
      name: "description",
      label: "Description",
      kind: "Text",
      order_weight: 2000,
    }),
    generateAttributeSchema({
      name: "internal_note",
      label: "Internal note",
      kind: "Text",
      display: "extra",
      order_weight: 3000,
    }),
  ],
  relationships: [],
});

const seedColumnsInUrl = ({ hidden, shown }: { hidden?: string; shown?: string }) => {
  const search = new URLSearchParams();
  if (hidden) search.set("hide_columns", hidden);
  if (shown) search.set("show_columns", shown);

  window.history.replaceState(null, "", `${window.location.pathname}?${search}`);
};

describe("ColumnsPicker", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", window.location.pathname);
  });

  test("shows no count while the view still shows the surface defaults", async () => {
    // GIVEN
    const schema = objectSchema;

    // WHEN
    const component = await render(<ColumnsPicker schema={schema} />);

    // THEN
    await expect.element(component.getByRole("button", { name: "Columns" })).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Columns" }).getByText(/^\d+$/))
      .not.toBeInTheDocument();
  });

  test("counts two hidden columns", async () => {
    // GIVEN
    seedColumnsInUrl({ hidden: "name,description" });

    // WHEN
    const component = await render(<ColumnsPicker schema={objectSchema} />);

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Columns" }).getByText("2", { exact: true }))
      .toBeVisible();
  });

  // The badge counts departures from the default column set, not hidden columns: a view showing an
  // extra column is customized too, and a hidden-count badge would show nothing there.
  test("counts a single revealed column", async () => {
    // GIVEN
    seedColumnsInUrl({ shown: "internal_note" });

    // WHEN
    const component = await render(<ColumnsPicker schema={objectSchema} />);

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Columns" }).getByText("1", { exact: true }))
      .toBeVisible();
  });
});
