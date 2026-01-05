import { describe, expect, test } from "vitest";
import { userEvent } from "vitest/browser";

import { render } from "../../../tests/components/render";
import { List } from "./list";

describe("List Component", () => {
  test("renders empty list state correctly", async () => {
    // GIVEN
    const component = await render(<List />);

    // THEN
    await expect.element(component.getByPlaceholder("Add a new item + hit 'enter'")).toBeVisible();
    await expect.element(component.getByText("Empty list")).toBeVisible();
  });

  test("renders with default values correctly", async () => {
    // GIVEN
    const defaultItems = ["item 1", "item 2"];
    const component = await render(<List defaultValue={defaultItems} />);

    // THEN
    await expect.element(component.getByText("item 1")).toBeVisible();
    await expect.element(component.getByText("item 2")).toBeVisible();
    await expect.element(component.baseElement).not.toHaveTextContent("Empty list");
  });

  test("adds new item when pressing enter", async () => {
    // GIVEN
    let items: string[] = [];
    const component = await render(<List onChange={(newItems) => (items = newItems)} />);
    const input = component.getByPlaceholder("Add a new item + hit 'enter'");

    // WHEN
    await input.fill("test item");
    await userEvent.keyboard("{enter}");

    // THEN
    await expect.element(component.getByText("test item")).toBeVisible();
    await expect.element(input).toHaveValue("");
    await expect.element(component.baseElement).not.toHaveTextContent("Empty list");
    expect(items).toEqual(["test item"]);
  });

  test("trims whitespace from input", async () => {
    // GIVEN
    let items: string[] = [];
    const component = await render(<List onChange={(newItems) => (items = newItems)} />);
    const input = component.getByPlaceholder("Add a new item + hit 'enter'");

    // WHEN
    await input.fill("  test item  ");
    await userEvent.keyboard("{enter}");

    // THEN
    await expect.element(component.getByText("test item", { exact: true })).toBeVisible();
    expect(items).toEqual(["test item"]);
  });

  test("handles empty string input correctly", async () => {
    // GIVEN
    const component = await render(<List />);
    const input = component.getByPlaceholder("Add a new item + hit 'enter'");

    // WHEN
    await input.fill("   ");
    await userEvent.keyboard("{enter}");

    // THEN
    await expect.element(component.getByText("Empty list")).toBeVisible();
  });

  test("prevents adding duplicate items and shows toast", async () => {
    // GIVEN
    const component = await render(<List defaultValue={["existing item"]} />);
    const input = component.getByPlaceholder("Add a new item + hit 'enter'");

    // WHEN
    await input.fill("existing item");
    await userEvent.keyboard("{enter}");

    // THEN
    await expect.element(component.getByText("Item already exists in the list")).toBeVisible();
    await expect.element(component.getByText("existing item")).toBeVisible();
  });

  test("removes item when clicking delete button", async () => {
    // GIVEN
    let items: string[] = ["test item"];
    const component = await render(
      <List defaultValue={items} onChange={(newItems) => (items = newItems)} />
    );

    // WHEN
    await component.getByRole("button", { name: "Remove" }).click();

    // THEN
    await expect.element(component.getByText("Empty list")).toBeVisible();
    await expect.element(component.baseElement).not.toHaveTextContent("test item");
    expect(items).toEqual([]);
  });

  test("removes middle item correctly", async () => {
    // GIVEN
    let items: string[] = ["first", "second", "third"];
    const component = await render(
      <List defaultValue={items} onChange={(newItems) => (items = newItems)} />
    );

    // WHEN
    await component
      .getByText("second")
      .locator("..")
      .getByRole("button", { name: "Remove" })
      .click();

    // THEN
    await expect.element(component.getByText("first")).toBeVisible();
    await expect.element(component.getByText("third")).toBeVisible();
    await expect.element(component.baseElement).not.toHaveTextContent("second");
    expect(items).toEqual(["first", "third"]);
  });

  test("disables all interactions when disabled prop is true", async () => {
    // GIVEN
    const component = await render(<List defaultValue={["test item"]} disabled={true} />);
    const input = component.getByPlaceholder("Add a new item + hit 'enter'");

    // THEN
    await expect.element(input).toBeDisabled();
    await expect.element(component.getByText("test item")).toBeVisible();
    await expect.poll(() => component.getByRole("button", { name: "Remove" }).query()).toBeNull();
  });

  test("handles controlled value prop correctly", async () => {
    // GIVEN
    const controlledItems = ["controlled item"];
    const component = await render(<List value={controlledItems} />);
    const input = component.getByPlaceholder("Add a new item + hit 'enter'");

    // WHEN
    await input.fill("new item");
    await userEvent.keyboard("{enter}");
    // THEN
    await expect.element(component.getByText("controlled item")).toBeVisible();
  });

  test("preserves order of items", async () => {
    // GIVEN
    let items: string[] = [];
    const component = await render(<List onChange={(newItems) => (items = newItems)} />);
    const input = component.getByPlaceholder("Add a new item + hit 'enter'");

    // WHEN
    await input.fill("first");
    await userEvent.keyboard("{enter}");
    await input.fill("second");
    await userEvent.keyboard("{enter}");
    await input.fill("third");
    await userEvent.keyboard("{enter}");

    // THEN
    expect(items).toEqual(["first", "second", "third"]);
  });

  test("handles special characters in items", async () => {
    // GIVEN
    let items: string[] = [];
    const component = await render(<List onChange={(newItems) => (items = newItems)} />);
    const input = component.getByPlaceholder("Add a new item + hit 'enter'");

    // WHEN
    await input.fill("!@#$%^&*()");
    await userEvent.keyboard("{enter}");

    // THEN
    await expect.element(component.getByText("!@#$%^&*()")).toBeVisible();
    expect(items).toEqual(["!@#$%^&*()"]);
  });
});
