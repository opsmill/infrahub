import { describe, expect, test } from "vitest";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import type { FormAttributeValue } from "@/shared/components/form/type";

import { TestForm } from "../../../../../tests/components/form.story";
import { render } from "../../../../../tests/components/render";
import BooleanField from "./boolean.field";

describe("Boolean Field Component", () => {
  test("renders null value with both checkbox cards unselected", async () => {
    // GIVEN
    let formValue;
    const component = await render(
      <TestForm onSubmit={(formData) => (formValue = formData)}>
        <BooleanField name="enabled" label="Enabled" defaultValue={DEFAULT_FORM_FIELD_VALUE} />
      </TestForm>
    );

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect.element(component.getByText("Enabled")).toBeVisible();
    await expect.element(component.getByRole("checkbox", { name: "True" })).not.toBeChecked();
    await expect.element(component.getByRole("checkbox", { name: "False" })).not.toBeChecked();
    expect(formValue).toEqual({ enabled: { source: null, value: null } });
  });

  test("sets true when true checkbox card is clicked", async () => {
    // GIVEN
    let formValue;
    const component = await render(
      <TestForm onSubmit={(formData) => (formValue = formData)}>
        <BooleanField name="enabled" label="Enabled" defaultValue={DEFAULT_FORM_FIELD_VALUE} />
      </TestForm>
    );

    // WHEN
    await component.getByText("True").click();
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect.element(component.getByRole("checkbox", { name: "True" })).toBeChecked();
    await expect.element(component.getByRole("checkbox", { name: "False" })).not.toBeChecked();
    expect(formValue).toEqual({ enabled: { source: { type: "user" }, value: true } });
  });

  test("sets false when false checkbox card is clicked", async () => {
    // GIVEN
    let formValue;
    const component = await render(
      <TestForm onSubmit={(formData) => (formValue = formData)}>
        <BooleanField name="enabled" label="Enabled" defaultValue={DEFAULT_FORM_FIELD_VALUE} />
      </TestForm>
    );

    // WHEN
    await component.getByText("False").click();
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect.element(component.getByRole("checkbox", { name: "True" })).not.toBeChecked();
    await expect.element(component.getByRole("checkbox", { name: "False" })).toBeChecked();
    expect(formValue).toEqual({ enabled: { source: { type: "user" }, value: false } });
  });

  test("clears to null when selected checkbox card is clicked again", async () => {
    // GIVEN
    let formValue;
    const defaultValue: FormAttributeValue = { source: { type: "schema" }, value: true };
    const component = await render(
      <TestForm onSubmit={(formData) => (formValue = formData)}>
        <BooleanField name="enabled" label="Enabled" defaultValue={defaultValue} />
      </TestForm>
    );

    // WHEN
    await component.getByText("True").click();
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect.element(component.getByRole("checkbox", { name: "True" })).not.toBeChecked();
    await expect.element(component.getByRole("checkbox", { name: "False" })).not.toBeChecked();
    expect(formValue).toEqual({ enabled: { source: { type: "user" }, value: null } });
  });

  test("required validation accepts false", async () => {
    // GIVEN
    const component = await render(
      <TestForm>
        <BooleanField
          name="enabled"
          label="Enabled"
          rules={{ required: true }}
          defaultValue={DEFAULT_FORM_FIELD_VALUE}
        />
      </TestForm>
    );

    // WHEN
    await component.getByText("False").click();
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect.poll(() => component.getByText("Required").query()).toBeNull();
  });

  test("required validation rejects null", async () => {
    // GIVEN
    const component = await render(
      <TestForm>
        <BooleanField
          name="enabled"
          label="Enabled"
          rules={{ required: true }}
          defaultValue={DEFAULT_FORM_FIELD_VALUE}
        />
      </TestForm>
    );

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect.element(component.getByText("Required")).toBeVisible();
  });
});
