import { ListBox, ListBoxItem, Tree, TreeItem, TreeItemContent } from "@infrahub/ui";
import { describe, expect, test } from "vitest";

import { render } from "../../../../tests/components/render";

// react-aria hands a render-props OBJECT to a `className` callback. `cn` is clsx-compatible, so
// forwarding that object into it emits every truthy key as a class name. Tree and ListBox both
// used to do exactly that, writing "level selectionMode state defaultClassName …" onto the
// element. composeAriaClassName already appends the consumer's className itself, so these
// components pass their styles as a plain string and must never reintroduce a callback that
// treats the render props as one.
const TREE_ITEM_RENDER_PROP_KEYS = [
  "hasAction",
  "hasChildItems",
  "level",
  "selectionMode",
  "selectionBehavior",
  "state",
  "defaultClassName",
];

const LIST_BOX_RENDER_PROP_KEYS = ["layout", "orientation", "state", "defaultClassName"];

const classListOf = async (element: Promise<Element> | Element): Promise<string[]> =>
  (await element).className.split(/\s+/).filter(Boolean);

describe("TreeItem className", () => {
  test("does not leak react-aria render-prop keys as class names", async () => {
    // GIVEN
    const component = await render(
      <Tree aria-label="Locations">
        <TreeItem id="north-america" textValue="North America">
          <TreeItemContent>North America</TreeItemContent>
        </TreeItem>
      </Tree>
    );

    // WHEN
    const classes = await classListOf(
      component.getByRole("row", { name: "North America" }).element()
    );

    // THEN
    expect(classes.filter((name: string) => TREE_ITEM_RENDER_PROP_KEYS.includes(name))).toEqual([]);
  });

  test("keeps the class the consumer passed as a string", async () => {
    // GIVEN
    const component = await render(
      <Tree aria-label="Locations">
        <TreeItem id="north-america" textValue="North America" className="bg-selected">
          <TreeItemContent>North America</TreeItemContent>
        </TreeItem>
      </Tree>
    );

    // WHEN
    const row = component.getByRole("row", { name: "North America" });

    // THEN
    await expect.element(row).toHaveClass("bg-selected");
  });

  // The styles are passed to composeAriaClassName as a plain string, so this covers the other
  // branch: react-aria also accepts className as a render-prop callback, and the consumer's
  // result still has to survive.
  test("keeps the class the consumer passed as a callback", async () => {
    // GIVEN
    const component = await render(
      <Tree aria-label="Locations">
        <TreeItem
          id="north-america"
          textValue="North America"
          className={({ isSelected }: { isSelected: boolean }) =>
            isSelected ? "bg-selected" : "bg-unselected"
          }
        >
          <TreeItemContent>North America</TreeItemContent>
        </TreeItem>
      </Tree>
    );

    // WHEN
    const row = component.getByRole("row", { name: "North America" });

    // THEN
    await expect.element(row).toHaveClass("bg-unselected");
  });
});

describe("ListBox className", () => {
  test("does not leak react-aria render-prop keys as class names", async () => {
    // GIVEN
    const component = await render(
      <ListBox aria-label="Options">
        <ListBoxItem id="a" textValue="A">
          A
        </ListBoxItem>
      </ListBox>
    );

    // WHEN
    const classes = await classListOf(component.getByRole("listbox").element());

    // THEN
    expect(classes.filter((name: string) => LIST_BOX_RENDER_PROP_KEYS.includes(name))).toEqual([]);
  });

  test("keeps the class the consumer passed as a string", async () => {
    // GIVEN
    const component = await render(
      <ListBox aria-label="Options" className="max-h-72">
        <ListBoxItem id="a" textValue="A">
          A
        </ListBoxItem>
      </ListBox>
    );

    // WHEN
    const listBox = component.getByRole("listbox");

    // THEN
    await expect.element(listBox).toHaveClass("max-h-72");
  });

  test("keeps the class the consumer passed as a callback", async () => {
    // GIVEN
    const component = await render(
      <ListBox
        aria-label="Options"
        className={({ isEmpty }: { isEmpty: boolean }) => (isEmpty ? "is-empty" : "has-options")}
      >
        <ListBoxItem id="a" textValue="A">
          A
        </ListBoxItem>
      </ListBox>
    );

    // WHEN
    const listBox = component.getByRole("listbox");

    // THEN
    await expect.element(listBox).toHaveClass("has-options");
  });
});
