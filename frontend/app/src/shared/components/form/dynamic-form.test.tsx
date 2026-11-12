import { describe, expect, test, vi } from "vitest";

import DynamicForm from "@/shared/components/form/dynamic-form";
import type { DynamicFieldProps, FormFieldValue } from "@/shared/components/form/type";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { isRequired } from "@/shared/components/form/utils/validation";

import type { AttributeSchema } from "@/entities/schema/domain/model/schema";

import { render } from "../../../../tests/components/render";
import { buildFormField } from "../../../../tests/fake/form";
import {
  generateAttributeSchema,
  generateContainerSchema,
  generateProfileSchema,
  generateTemplateSchema,
} from "../../../../tests/fake/schema";

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

  test("renders the Details panel first, then one panel per container in order weight order", async () => {
    const component = await render(<DynamicForm fields={fields} sections={[lacp, layer2]} />);

    await expect.element(component.getByRole("region", { name: "LACP" })).toBeVisible();
    const regionNames = component
      .getByRole("region")
      .elements()
      .map((region) => region.querySelector("h2")?.textContent);
    expect(regionNames).toEqual(["Details", "Layer 2", "LACP"]);
    await expect
      .element(component.getByRole("region", { name: "Details" }).getByLabelText("name"))
      .toBeVisible();
    await expect
      .element(component.getByRole("region", { name: "Layer 2" }).getByLabelText("vlan"))
      .toBeVisible();
  });

  test("renders the Profile panel of a profile above Details", async () => {
    const profileSchema = generateProfileSchema({
      containers: [
        generateContainerSchema({ name: "builtin_profile", label: "Profile", order_weight: -100 }),
        layer2,
      ],
      attributes: [
        generateAttributeSchema({
          name: "profile_name",
          label: "Profile Name",
          order_weight: 100,
          container: "builtin_profile",
        }),
        generateAttributeSchema({
          name: "profile_priority",
          label: "Profile Priority",
          kind: "Number",
          order_weight: 200,
          container: "builtin_profile",
        }),
        generateAttributeSchema({ name: "name", label: "Name", order_weight: 300 }),
        generateAttributeSchema({
          name: "vlan",
          label: "VLAN",
          order_weight: 400,
          container: "layer2",
        }),
      ],
      relationships: [],
    });
    const component = await render(
      <DynamicForm
        fields={getFormFieldsFromSchema({ schema: profileSchema })}
        sections={profileSchema.containers}
      />
    );

    const profile = component.getByRole("region", { name: "Profile", exact: true });
    await expect.element(profile.getByLabelText("Profile Name")).toBeVisible();
    await expect.element(profile.getByLabelText("Profile Priority")).toBeVisible();
    const regionNames = component
      .getByRole("region")
      .elements()
      .map((region) => region.querySelector("h2")?.textContent);
    expect(regionNames).toEqual(["Profile", "Details", "Layer 2"]);
  });

  test("renders the Template panel of an object template above Details", async () => {
    const templateSchema = generateTemplateSchema({
      containers: [
        generateContainerSchema({
          name: "builtin_template",
          label: "Template",
          order_weight: -100,
        }),
        layer2,
      ],
      attributes: [
        generateAttributeSchema({
          name: "template_name",
          label: "Template Name",
          order_weight: 100,
          container: "builtin_template",
        }),
        generateAttributeSchema({ name: "name", label: "Name", order_weight: 300 }),
        generateAttributeSchema({
          name: "vlan",
          label: "VLAN",
          order_weight: 400,
          container: "layer2",
        }),
      ],
      relationships: [],
    });
    const component = await render(
      <DynamicForm
        fields={getFormFieldsFromSchema({ schema: templateSchema })}
        sections={templateSchema.containers}
      />
    );

    const template = component.getByRole("region", { name: "Template", exact: true });
    await expect.element(template.getByLabelText("Template Name")).toBeVisible();
    const regionNames = component
      .getByRole("region")
      .elements()
      .map((region) => region.querySelector("h2")?.textContent);
    expect(regionNames).toEqual(["Template", "Details", "Layer 2"]);
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

  test("puts the fields of a container named details in the Details panel", async () => {
    // GIVEN a declared container that takes the name of the built-in Details section
    const details = generateContainerSchema({ name: "details", label: "General" });
    const component = await render(
      <DynamicForm
        fields={[
          buildAttributeField("mode", { container: "details" }),
          buildAttributeField("lag_mode", { container: "lacp" }),
        ]}
        sections={[details, lacp]}
      />
    );

    await expect
      .element(component.getByRole("region", { name: "Details" }).getByLabelText("mode"))
      .toBeVisible();
    expect(component.getByRole("region", { name: "General" }).elements()).toHaveLength(0);
  });
});
