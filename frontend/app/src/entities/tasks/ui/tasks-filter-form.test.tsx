import { describe, expect, test } from "vitest";

import { render } from "../../../../tests/components/render";
import { TasksFilterForm } from "./tasks-filter-form";

// Branch, State, then Type — the third dropdown in the form.
const TYPE_FIELD_INDEX = 2;

describe("TasksFilterForm", () => {
  test("offers every workflow type, labelling internal workflows as System", async () => {
    // GIVEN
    const component = await render(<TasksFilterForm filters={[]} />);

    // WHEN
    await component.getByRole("combobox").nth(TYPE_FIELD_INDEX).click();

    // THEN
    await expect.element(component.getByRole("option", { name: "Core" })).toBeVisible();
    await expect.element(component.getByRole("option", { name: "User" })).toBeVisible();
    await expect.element(component.getByRole("option", { name: "System" })).toBeVisible();
    await expect
      .element(component.getByRole("option", { name: "Internal" }))
      .not.toBeInTheDocument();
  });

  test("leaves the type unset so that no type is not the same request as all types", async () => {
    // GIVEN
    const component = await render(<TasksFilterForm filters={[]} />);

    // WHEN
    const typeField = component.getByRole("combobox").nth(TYPE_FIELD_INDEX);

    // THEN
    await expect.element(component.getByText("Type", { exact: true })).toBeVisible();
    await expect.element(typeField).toHaveTextContent("");
  });
});
