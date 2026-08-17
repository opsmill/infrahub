import { Tree, TreeItem, TreeItemContent } from "@infrahub/ui";
import { describe, expect, test } from "vitest";

import { render } from "../../../../../tests/components/render";

// react-aria passes a render-props OBJECT to a `className` callback. `cn` is clsx-compatible,
// so forwarding that object into it emits every truthy key as a class name. TreeItem used to do
// exactly that, leaking `hasAction hasChildItems level selectionMode ...` onto every row.
const RENDER_PROP_KEYS = [
  "hasAction",
  "hasChildItems",
  "level",
  "selectionMode",
  "selectionBehavior",
  "state",
  "defaultClassName",
];

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
    const row = component.getByRole("row", { name: "North America" });

    // THEN
    const classes: string[] = (await row.element()).className.split(/\s+/).filter(Boolean);
    expect(classes.filter((name: string) => RENDER_PROP_KEYS.includes(name))).toEqual([]);
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
  // result still has to survive and win the merge.
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
