import { expect, test } from "@playwright/experimental-ct-react";
import { List } from "./list";

test.describe("List Component", () => {
  test("renders empty list state correctly", async ({ mount }) => {
    // GIVEN
    const component = await mount(<List />);

    // THEN
    await expect(component.getByPlaceholder("Add a new item + hit 'enter'")).toBeVisible();
    await expect(component.getByText("Empty list")).toBeVisible();
  });

  test("adds new item when pressing enter", async ({ mount }) => {
    // GIVEN
    let items: string[] = [];
    const component = await mount(<List onChange={(newItems) => (items = newItems)} />);
    const input = component.getByPlaceholder("Add a new item + hit 'enter'");

    // WHEN
    await input.fill("test item");
    await input.press("Enter");

    // THEN
    await expect(component.getByText("test item")).toBeVisible();
    await expect(input).toHaveValue("");
    await expect(component.getByText("Empty list")).not.toBeVisible();
    expect(items).toEqual(["test item"]);
  });

  test("prevents adding duplicate items and shows toast", async ({ mount }) => {
    // GIVEN
    const component = await mount(<List defaultValue={["existing item"]} />);
    const input = component.getByPlaceholder("Add a new item + hit 'enter'");

    // WHEN
    await input.fill("existing item");
    await input.press("Enter");

    // THEN
    await expect(component.getByText("Item already exists in the list")).toBeVisible();
    await expect(component.getByText("existing item")).toBeVisible();
  });

  test("removes item when clicking delete button", async ({ mount }) => {
    // GIVEN
    let items: string[] = ["test item"];
    const component = await mount(
      <List defaultValue={items} onChange={(newItems) => (items = newItems)} />
    );

    // WHEN
    await component.getByRole("button", { name: "Remove" }).click();

    // THEN
    await expect(component.getByText("Empty list")).toBeVisible();
    await expect(component.getByText("test item")).not.toBeVisible();
    expect(items).toEqual([]);
  });

  test("disables all interactions when disabled prop is true", async ({ mount }) => {
    // GIVEN
    const component = await mount(<List defaultValue={["test item"]} disabled={true} />);
    const input = component.getByPlaceholder("Add a new item + hit 'enter'");

    // THEN
    await expect(input).toBeDisabled();
    await expect(component.getByText("test item")).toBeVisible();
    await expect(component.getByRole("button", { name: "Remove" })).not.toBeVisible();
  });

  test("handles empty string input correctly", async ({ mount }) => {
    // GIVEN
    const component = await mount(<List />);
    const input = component.getByPlaceholder("Add a new item + hit 'enter'");

    // WHEN
    await input.fill("   ");
    await input.press("Enter");

    // THEN
    await expect(component.getByText("Empty list")).toBeVisible();
  });

  test("trims whitespace from input", async ({ mount }) => {
    // GIVEN
    let items: string[] = [];
    const component = await mount(<List onChange={(newItems) => (items = newItems)} />);
    const input = component.getByPlaceholder("Add a new item + hit 'enter'");

    // WHEN
    await input.fill("  test item  ");
    await input.press("Enter");

    // THEN
    await expect(component.getByText("test item")).toBeVisible();
    expect(items).toEqual(["test item"]);
  });

  test("handles controlled value prop correctly", async ({ mount }) => {
    // GIVEN
    const controlledItems = ["controlled item"];
    const component = await mount(<List value={controlledItems} />);
    const input = component.getByPlaceholder("Add a new item + hit 'enter'");

    // WHEN
    await input.fill("new item");
    await input.press("Enter");

    // THEN
    await expect(component.getByText("controlled item")).toBeVisible();
  });

  test("preserves order of items", async ({ mount }) => {
    // GIVEN
    let items: string[] = [];
    const component = await mount(<List onChange={(newItems) => (items = newItems)} />);
    const input = component.getByPlaceholder("Add a new item + hit 'enter'");

    // WHEN
    await input.fill("first");
    await input.press("Enter");
    await input.fill("second");
    await input.press("Enter");
    await input.fill("third");
    await input.press("Enter");

    // THEN
    expect(items).toEqual(["first", "second", "third"]);
  });

  test("handles special characters in items", async ({ mount }) => {
    // GIVEN
    let items: string[] = [];
    const component = await mount(<List onChange={(newItems) => (items = newItems)} />);
    const input = component.getByPlaceholder("Add a new item + hit 'enter'");

    // WHEN
    await input.fill("!@#$%^&*()");
    await input.press("Enter");

    // THEN
    await expect(component.getByText("!@#$%^&*()")).toBeVisible();
    expect(items).toEqual(["!@#$%^&*()"]);
  });
});
