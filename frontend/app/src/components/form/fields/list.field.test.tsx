import ListField from "@/components/form/fields/list.field";
import { FormAttributeValue } from "@/components/form/type";
import { expect, test } from "@playwright/experimental-ct-react";
import { TestForm } from "../../../../tests/components/form.story";

test.describe("List Field Component", () => {
  test("renders empty list field correctly", async ({ mount }) => {
    // GIVEN
    let formValue;
    const component = await mount(
      <TestForm onSubmit={(formData) => (formValue = formData)}>
        <ListField name="field1" label="Test List" />
      </TestForm>
    );

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect(component.getByText("Test List")).toBeVisible();
    await expect(component.getByLabel("Test List")).toBeVisible();
    await expect(component.getByPlaceholder("Add a new item + hit 'enter'")).toBeVisible();
    await expect(component.getByText("Empty list")).toBeVisible();
    expect(formValue).toEqual({ field1: { source: null, value: null } });
  });

  test("renders with default values from schema correctly", async ({ mount }) => {
    // GIVEN
    let formValue;
    const defaultValue: FormAttributeValue = {
      source: { type: "schema" },
      value: ["item 1", "item 2"],
    };
    const component = await mount(
      <TestForm onSubmit={(formData) => (formValue = formData)}>
        <ListField name="field1" label="Test List" defaultValue={defaultValue} />
      </TestForm>
    );

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect(component.getByText("item 1")).toBeVisible();
    await expect(component.getByText("item 2")).toBeVisible();
    expect(formValue).toEqual({
      field1: { source: { type: "schema" }, value: ["item 1", "item 2"] },
    });
  });

  test("renders with default values from user correctly", async ({ mount }) => {
    // GIVEN
    let formValue;
    const defaultValue: FormAttributeValue = {
      source: { type: "user" },
      value: ["user item 1", "user item 2"],
    };
    const component = await mount(
      <TestForm onSubmit={(formData) => (formValue = formData)}>
        <ListField name="field1" label="Test List" defaultValue={defaultValue} />
      </TestForm>
    );

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect(component.getByText("user item 1")).toBeVisible();
    await expect(component.getByText("user item 2")).toBeVisible();
    expect(formValue).toEqual({
      field1: { source: { type: "user" }, value: ["user item 1", "user item 2"] },
    });
  });

  test("shows required validation message when empty", async ({ mount }) => {
    // GIVEN
    const component = await mount(
      <TestForm>
        <ListField name="test" label="Test List" rules={{ required: true }} />
      </TestForm>
    );

    // WHEN
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    await expect(component.getByText("Required")).toBeVisible();
  });

  test("passes validation when required field has items", async ({ mount }) => {
    // GIVEN
    const defaultValue: FormAttributeValue = { source: { type: "user" }, value: ["test item"] };
    const component = await mount(
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
    await expect(component.getByText("Required")).not.toBeVisible();
  });

  test("displays description on hover when provided", async ({ mount, page }) => {
    // GIVEN
    const component = await mount(
      <TestForm>
        <ListField name="test" label="Test List" description="This is a test description" />
      </TestForm>
    );

    // WHEN
    await component.getByRole("button", { name: "?" }).hover();

    // THEN
    await expect(page.getByText("This is a test description")).toBeVisible();
  });

  test("shows unique indicator when unique prop is true", async ({ mount }) => {
    // GIVEN
    const component = await mount(
      <TestForm>
        <ListField name="test" label="Test List" unique={true} />
      </TestForm>
    );

    // THEN
    await expect(component.getByText("must be unique")).toBeVisible();
  });

  test("updates form value when items change", async ({ mount }) => {
    // GIVEN
    let formValue;
    const defaultValue: FormAttributeValue = { source: { type: "user" }, value: [] };
    const component = await mount(
      <TestForm onSubmit={(formData) => (formValue = formData)}>
        <ListField
          name="field1"
          label="Test List"
          defaultValue={defaultValue}
          onChange={(value) => (formValue = value)}
        />
      </TestForm>
    );
    const input = component.getByLabel("Test List");

    // WHEN
    await input.fill("test item");
    await input.press("Enter");
    await component.getByRole("button", { name: "Submit" }).click();

    // THEN
    expect(formValue).toEqual({ field1: { source: { type: "user" }, value: ["test item"] } });
  });
});
