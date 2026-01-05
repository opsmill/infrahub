import { describe, expect, test } from "vitest";
import { userEvent } from "vitest/browser";

import ListField from "@/shared/components/form/fields/list.field";
import type { FormAttributeValue } from "@/shared/components/form/type";

import { TestForm } from "../../../../../tests/components/form.story";
import { render } from "../../../../../tests/components/render";

describe("List Field Component", () => {
  test("renders empty list field correctly", async () => {
    // GIVEN
    let formValue;
    const component = await render(
      <TestForm onSubmit={(formData) => (formValue = formData)}>
        <ListField name="field1" label="Test List" />
      </TestForm>
    );

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect.element(component.getByText("Test List")).toBeVisible();
    await expect.element(component.getByLabelText("Test List")).toBeVisible();
    await expect.element(component.getByPlaceholder("Add a new item + hit 'enter'")).toBeVisible();
    await expect.element(component.getByText("Empty list")).toBeVisible();
    expect(formValue).toEqual({ field1: { source: null, value: null } });
  });

  test("renders with default values from schema correctly", async () => {
    // GIVEN
    let formValue;
    const defaultValue: FormAttributeValue = {
      source: { type: "schema" },
      value: ["item 1", "item 2"],
    };
    const component = await render(
      <TestForm onSubmit={(formData) => (formValue = formData)}>
        <ListField name="field1" label="Test List" defaultValue={defaultValue} />
      </TestForm>
    );

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect.element(component.getByText("item 1")).toBeVisible();
    await expect.element(component.getByText("item 2")).toBeVisible();
    expect(formValue).toEqual({
      field1: { source: { type: "schema" }, value: ["item 1", "item 2"] },
    });
  });

  test("renders with default values from user correctly", async () => {
    // GIVEN
    let formValue;
    const defaultValue: FormAttributeValue = {
      source: { type: "user" },
      value: ["user item 1", "user item 2"],
    };
    const component = await render(
      <TestForm onSubmit={(formData) => (formValue = formData)}>
        <ListField name="field1" label="Test List" defaultValue={defaultValue} />
      </TestForm>
    );

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect.element(component.getByText("user item 1")).toBeVisible();
    await expect.element(component.getByText("user item 2")).toBeVisible();
    expect(formValue).toEqual({
      field1: { source: { type: "user" }, value: ["user item 1", "user item 2"] },
    });
  });

  test("shows required validation message when empty", async () => {
    // GIVEN
    const component = await render(
      <TestForm>
        <ListField name="test" label="Test List" rules={{ required: true }} />
      </TestForm>
    );

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect.element(component.getByText("Required")).toBeVisible();
  });

  test("passes validation when required field has items", async () => {
    // GIVEN
    const defaultValue: FormAttributeValue = { source: { type: "user" }, value: ["test item"] };
    const component = await render(
      <TestForm>
        <ListField
          name="test"
          label="Test List"
          rules={{ required: true }}
          defaultValue={defaultValue}
        />
      </TestForm>
    );

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect.poll(() => component.getByText("Required").query()).toBeNull();
  });

  test("displays description on hover when provided", async () => {
    // GIVEN
    const component = await render(
      <TestForm>
        <ListField name="test" label="Test List" description="This is a test description" />
      </TestForm>
    );

    // WHEN
    await component.getByRole("button", { name: "?" }).hover();

    // THEN
    await expect.element(component.getByText("This is a test description")).toBeVisible();
  });

  test("shows unique indicator when unique prop is true", async () => {
    // GIVEN
    const component = await render(
      <TestForm>
        <ListField name="test" label="Test List" unique={true} />
      </TestForm>
    );

    // THEN
    await expect.element(component.getByText("must be unique")).toBeVisible();
  });

  test("updates form value when items change", async () => {
    // GIVEN
    let formValue;
    const defaultValue: FormAttributeValue = { source: { type: "user" }, value: [] };
    const component = await render(
      <TestForm onSubmit={(formData) => (formValue = formData)}>
        <ListField
          name="field1"
          label="Test List"
          defaultValue={defaultValue}
          onChange={(value) => (formValue = value)}
        />
      </TestForm>
    );
    const input = component.getByLabelText("Test List");

    // WHEN
    await input.fill("test item");
    await userEvent.keyboard("{enter}");
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    expect(formValue).toEqual({ field1: { source: { type: "user" }, value: ["test item"] } });
  });

  test("returns null when list is cleared", async () => {
    // GIVEN
    let formValue;
    const defaultValue: FormAttributeValue = {
      source: { type: "user" },
      value: ["item 1", "item 2"],
    };
    const component = await render(
      <TestForm onSubmit={(formData) => (formValue = formData)}>
        <ListField name="field1" label="Test List" defaultValue={defaultValue} />
      </TestForm>
    );

    // WHEN
    await component.getByRole("button", { name: "Remove item 1" }).click();
    await component.getByRole("button", { name: "Remove item 2" }).click();
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    expect(formValue).toEqual({
      field1: { source: { type: "user" }, value: null },
    });
  });
});
