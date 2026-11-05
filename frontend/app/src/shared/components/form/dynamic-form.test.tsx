import { describe, expect, test, vi } from "vitest";

import DynamicForm from "@/shared/components/form/dynamic-form";
import type { DynamicFieldProps, FormFieldValue } from "@/shared/components/form/type";
import { isRequired } from "@/shared/components/form/utils/validation";

import type { AttributeSchema } from "@/entities/schema/domain/model/schema";

import { render } from "../../../../tests/components/render";
import { buildFormField } from "../../../../tests/fake/form";
import { generateAttributeSchema, generateContainerSchema } from "../../../../tests/fake/schema";

function buildAttributeField(
  name: string,
  attributeOverride: Partial<AttributeSchema> = {},
  fieldOverride: Partial<DynamicFieldProps> = {}
): DynamicFieldProps {
  return buildFormField({
    name,
    label: name,
    defaultValue: { source: { type: "user" }, value: `${name} value` },
    rules: {},
    unique: false,
    attribute: generateAttributeSchema({ name, label: name, ...attributeOverride }),
    ...fieldOverride,
  } as Partial<DynamicFieldProps>);
}

const lacp = generateContainerSchema({ name: "lacp", label: "LACP", order_weight: 2000 });
const layer2 = generateContainerSchema({ name: "layer2", label: "Layer 2", order_weight: 1000 });

const fields = [
  buildAttributeField("mode", { container: "lacp" }),
  buildAttributeField("name"),
  buildAttributeField("vlan", { container: "layer2" }),
];

describe("DynamicForm", () => {
  test("renders a flat list without sections", async () => {
    const component = await render(<DynamicForm fields={fields} />);

    await expect.element(component.getByLabelText("mode")).toBeVisible();
    expect(component.getByRole("region").elements()).toHaveLength(0);
  });

  test("renders one panel per section headed by the container label in order weight order", async () => {
    const component = await render(<DynamicForm fields={fields} sections={[lacp, layer2]} />);

    await expect.element(component.getByRole("region", { name: "LACP" })).toBeVisible();
    const regionNames = component
      .getByRole("region")
      .elements()
      .map((region) => region.querySelector("h2")?.textContent);
    expect(regionNames).toEqual(["Details", "Layer 2", "LACP"]);
    await expect
      .element(component.getByRole("region", { name: "Layer 2" }).getByLabelText("vlan"))
      .toBeVisible();
  });

  test("renders the Details panel first", async () => {
    const component = await render(<DynamicForm fields={fields} sections={[lacp, layer2]} />);

    const details = component.getByRole("region", { name: "Details" });
    await expect.element(details).toBeVisible();
    expect(component.getByRole("region").elements()[0]).toBe(details.element());
    await expect.element(details.getByLabelText("name")).toBeVisible();
  });

  test("renders no panel when all its fields are filtered out", async () => {
    const component = await render(
      <DynamicForm
        fields={fields.filter((field) => field.name !== "vlan")}
        sections={[lacp, layer2]}
      />
    );

    await expect.element(component.getByRole("region", { name: "LACP" })).toBeVisible();
    expect(component.getByRole("region", { name: "Layer 2" }).elements()).toHaveLength(0);
  });

  test("keeps a collapsed container expanded", async () => {
    const collapsed = generateContainerSchema({ name: "lacp", label: "LACP", collapsed: true });
    const component = await render(<DynamicForm fields={fields} sections={[collapsed]} />);

    const region = component.getByRole("region", { name: "LACP" });
    await expect.element(region.getByLabelText("mode")).toBeVisible();
    expect(region.getByRole("button", { name: "LACP" }).elements()).toHaveLength(0);
  });

  test("renders a display extra field inside its panel", async () => {
    const component = await render(
      <DynamicForm
        fields={[...fields, buildAttributeField("rate", { container: "lacp", display: "extra" })]}
        sections={[lacp]}
      />
    );

    await expect
      .element(component.getByRole("region", { name: "LACP" }).getByLabelText("rate"))
      .toBeVisible();
  });

  test("sends the same payload with and without sections", async () => {
    const flatSubmit = vi.fn<(data: Record<string, FormFieldValue>) => void>();
    const flat = await render(<DynamicForm fields={fields} onSubmit={flatSubmit} />);
    await flat.getByRole("button", { name: "Save" }).click();
    await vi.waitFor(() => expect(flatSubmit).toHaveBeenCalledOnce());
    await flat.unmount();

    const sectionedSubmit = vi.fn<(data: Record<string, FormFieldValue>) => void>();
    const sectioned = await render(
      <DynamicForm fields={fields} sections={[lacp, layer2]} onSubmit={sectionedSubmit} />
    );
    await sectioned.getByRole("button", { name: "Save" }).click();
    await vi.waitFor(() => expect(sectionedSubmit).toHaveBeenCalledOnce());

    expect(sectionedSubmit.mock.calls[0]![0]).toEqual(flatSubmit.mock.calls[0]![0]);
  });

  test("shows a validation error inside its panel", async () => {
    const requiredField = buildAttributeField("mode", { container: "lacp" }, {
      defaultValue: { source: null, value: null },
      rules: { validate: { required: isRequired } },
    } as Partial<DynamicFieldProps>);
    const onSubmit = vi.fn<(data: Record<string, FormFieldValue>) => void>();
    const component = await render(
      <DynamicForm fields={[requiredField]} sections={[lacp]} onSubmit={onSubmit} />
    );

    await component.getByRole("button", { name: "Save" }).click();

    await expect
      .element(component.getByRole("region", { name: "LACP" }).getByText("Required"))
      .toBeVisible();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
