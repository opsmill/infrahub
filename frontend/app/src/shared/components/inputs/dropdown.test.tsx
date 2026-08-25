import { afterEach, describe, expect, test } from "vitest";

import { store } from "@/shared/stores";

import type { AttributeSchema, ModelSchema } from "@/entities/schema/domain/model/schema";
import { namespacesAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../tests/components/render";
import { Dropdown } from "./dropdown";

const field = { name: "status" } as AttributeSchema;
const items = [
  { value: "default", label: "Default" },
  { value: "internal", label: "Internal" },
];

describe("Dropdown delete button", () => {
  afterEach(() => {
    store.set(namespacesAtom, []);
  });

  test("hides the delete button when the namespace is not user-editable", async () => {
    // GIVEN a field on a non-user-editable namespace (e.g. Core)
    store.set(namespacesAtom, [{ name: "Core", user_editable: false }]);
    const schema = { kind: "CoreStandardGroup", namespace: "Core" } as ModelSchema;

    // WHEN the dropdown options are shown
    const component = await render(
      <Dropdown
        items={items}
        value="default"
        schema={schema}
        field={field}
        onChange={() => {}}
        defaultOpen
      />
    );

    // THEN no delete button is rendered for the protected options
    await expect.element(component.getByText("Internal")).toBeVisible();
    await expect
      .poll(() => component.getByRole("button", { name: "Delete option" }).query())
      .toBeNull();
  });

  test("shows the delete button when the namespace is user-editable", async () => {
    // GIVEN a field on a user-editable namespace
    store.set(namespacesAtom, [{ name: "Builtin", user_editable: true }]);
    const schema = { kind: "MyCustomNode", namespace: "Builtin" } as ModelSchema;

    // WHEN the dropdown options are shown
    const component = await render(
      <Dropdown
        items={items}
        value="default"
        schema={schema}
        field={field}
        onChange={() => {}}
        defaultOpen
      />
    );

    // THEN a delete button is rendered for the editable options
    await expect.element(component.getByText("Internal")).toBeVisible();
    await expect
      .element(component.getByRole("button", { name: "Delete option" }).first())
      .toBeVisible();
  });
});

describe("Dropdown popover width", () => {
  test("keeps the option popover within the trigger width when a choice description is long", async () => {
    // GIVEN a dropdown in a narrow container whose option has a description far wider than the field
    const longDescriptionItems = [
      {
        value: "vm",
        label: "Virtual Machine",
        description:
          "Representing a hypervisor that hosts virtual machines running many isolated guest operating systems.",
      },
      {
        value: "baremetal",
        label: "Bare Metal",
        description:
          "Representing a workload directly on the hardware, without a hypervisor and with no virtualization layer.",
      },
    ];

    // WHEN the dropdown is opened
    const component = await render(
      <div style={{ width: 200 }}>
        <Dropdown items={longDescriptionItems} value="vm" onChange={() => {}} defaultOpen />
      </div>
    );
    await expect.element(component.getByPlaceholder("Filter...")).toBeVisible();

    // THEN the popover does not grow wider than its trigger, so its left edge is never clipped
    const trigger = component.baseElement.querySelector<HTMLElement>('button[role="combobox"]');
    if (!trigger) throw new Error("Trigger button was not found in the DOM");
    const popover = component.baseElement.querySelector<HTMLElement>("[data-react-aria-top-layer]");
    if (!popover) throw new Error("Popover content element was not found in the DOM");

    const triggerWidth = trigger.getBoundingClientRect().width;
    const popoverWidth = popover.getBoundingClientRect().width;

    expect(popoverWidth).toBeLessThanOrEqual(triggerWidth + 1);
  });
});
