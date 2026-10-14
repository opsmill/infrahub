import { beforeEach, describe, expect, it } from "vitest";

import { QSP } from "@/shared/config/qsp";

import { AttributeFilterForm } from "@/entities/nodes/object/ui/filters/attribute-filter-form";
import { FILTER_CONDITION } from "@/entities/nodes/object/ui/filters/filter-condition-select";

import { render } from "../../../../../../tests/components/render";
import { generateAttributeSchema } from "../../../../../../tests/fake/schema";

const NAME_SCHEMA = generateAttributeSchema({ name: "name", label: "Branch", kind: "Text" });

function seedFilters(filters: { name: string; value: unknown }[]) {
  window.history.replaceState(
    null,
    "",
    `/?${QSP.FILTER}=${encodeURIComponent(JSON.stringify(filters))}`
  );
}

function getAppliedFilters(): { name: string; value: unknown }[] {
  const raw = new URLSearchParams(window.location.search).get(QSP.FILTER);

  return raw ? JSON.parse(raw) : [];
}

// A caller that narrows the offered conditions leaves the form unable to show a filter set under one
// of the others; applying the form must not be how that filter disappears.
describe("AttributeFilterForm", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", window.location.pathname);
  });

  it("keeps an 'is any of' filter it can only show as 'contains'", async () => {
    // GIVEN
    seedFilters([{ name: "name__values", value: ["main", "staging"] }]);
    const component = await render(
      <AttributeFilterForm
        attributeSchema={NAME_SCHEMA}
        filterConditions={[FILTER_CONDITION.CONTAINS]}
      />
    );

    // WHEN
    await component.getByRole("button", { name: "Apply" }).click();

    // THEN
    expect(getAppliedFilters()).toEqual([{ name: "name__values", value: ["main", "staging"] }]);
  });

  it("keeps an emptiness filter it cannot show at all", async () => {
    // GIVEN
    seedFilters([{ name: "name__isnull", value: true }]);
    const component = await render(
      <AttributeFilterForm
        attributeSchema={NAME_SCHEMA}
        filterConditions={[FILTER_CONDITION.CONTAINS]}
      />
    );

    // WHEN
    await component.getByRole("button", { name: "Apply" }).click();

    // THEN
    expect(getAppliedFilters()).toEqual([{ name: "name__isnull", value: true }]);
  });

  it("still clears a filter the user empties themselves", async () => {
    // GIVEN
    seedFilters([{ name: "name__value", value: "release" }]);
    const component = await render(
      <AttributeFilterForm
        attributeSchema={NAME_SCHEMA}
        filterConditions={[FILTER_CONDITION.CONTAINS]}
      />
    );

    // WHEN
    await component.getByRole("textbox").fill("");
    await component.getByRole("button", { name: "Apply" }).click();

    // THEN
    expect(getAppliedFilters()).toEqual([]);
  });
});
