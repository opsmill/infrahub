import { describe, expect, test } from "vitest";

import type { NodeAttribute } from "@/entities/nodes/object/domain/model/node";

import { render } from "../../../../../../../tests/components/render";
import { generateAttributeSchema } from "../../../../../../../tests/fake/schema";
import { TableAttributeCell } from "./table-attribute-cell";

const attribute = (value: unknown) => ({ value }) as NodeAttribute;

const uplinks = Array.from({ length: 30 }, (_, index) => `Ethernet1/${index + 1}`);

describe("TableAttributeCell", () => {
  test("shows the count of a List value", async () => {
    // GIVEN
    const schema = generateAttributeSchema({ name: "uplinks", kind: "List", label: "Uplinks" });

    // WHEN
    const component = await render(
      <TableAttributeCell attributeSchema={schema} attributeData={attribute(uplinks)} />
    );

    // THEN
    await expect
      .element(component.getByRole("button", { name: "View all 30 elements of Uplinks" }))
      .toBeVisible();
  });

  test("opens every element of a List value in a dialog", async () => {
    // GIVEN
    const schema = generateAttributeSchema({ name: "uplinks", kind: "List", label: "Uplinks" });
    const component = await render(
      <TableAttributeCell attributeSchema={schema} attributeData={attribute(uplinks)} />
    );

    // WHEN
    await component.getByRole("button", { name: "View all 30 elements of Uplinks" }).click();

    // THEN
    await expect
      .element(component.getByRole("dialog").getByText("Ethernet1/30", { exact: true }))
      .toBeInTheDocument();
  });

  test("filters the elements in the List dialog", async () => {
    // GIVEN
    const schema = generateAttributeSchema({ name: "uplinks", kind: "List", label: "Uplinks" });
    const component = await render(
      <TableAttributeCell attributeSchema={schema} attributeData={attribute(uplinks)} />
    );
    await component.getByRole("button", { name: "View all 30 elements of Uplinks" }).click();

    // WHEN
    await component.getByRole("textbox", { name: "Filter elements" }).fill("1/2");

    // THEN
    await expect.element(component.getByText("11 of 30 elements")).toBeVisible();
  });

  test("opens the whole value of a JSON attribute from its preview", async () => {
    // GIVEN
    const schema = generateAttributeSchema({ name: "config", kind: "JSON", label: "Config" });
    const component = await render(
      <TableAttributeCell
        attributeSchema={schema}
        attributeData={attribute({ bgp: { asn: 65101 } })}
      />
    );

    // WHEN
    await component.getByRole("button", { name: "View Config JSON" }).click();

    // THEN
    await expect.element(component.getByRole("heading", { name: "Config · JSON" })).toBeVisible();
  });

  test("renders an Any array as a List", async () => {
    // GIVEN
    const schema = generateAttributeSchema({ name: "extra", kind: "Any", label: "Extra" });

    // WHEN
    const component = await render(
      <TableAttributeCell attributeSchema={schema} attributeData={attribute(["a", "b"])} />
    );

    // THEN
    await expect
      .element(component.getByRole("button", { name: "View all 2 elements of Extra" }))
      .toBeVisible();
  });

  test("renders an Any object as JSON", async () => {
    // GIVEN
    const schema = generateAttributeSchema({ name: "extra", kind: "Any", label: "Extra" });

    // WHEN
    const component = await render(
      <TableAttributeCell attributeSchema={schema} attributeData={attribute({ role: "spine" })} />
    );

    // THEN
    await expect.element(component.getByRole("button", { name: "View Extra JSON" })).toBeVisible();
  });

  test("hides a password value", async () => {
    // GIVEN
    const schema = generateAttributeSchema({ name: "secret", kind: "Password", label: "Secret" });

    // WHEN
    const component = await render(
      <TableAttributeCell attributeSchema={schema} attributeData={attribute("hunter2")} />
    );

    // THEN
    await expect.element(component.getByRole("img", { name: "Value set, hidden" })).toBeVisible();
    expect(component.container.textContent).not.toContain("hunter2");
  });

  test("renders an empty List as a dash", async () => {
    // GIVEN
    const schema = generateAttributeSchema({ name: "uplinks", kind: "List", label: "Uplinks" });

    // WHEN
    const component = await render(
      <TableAttributeCell attributeSchema={schema} attributeData={attribute([])} />
    );

    // THEN
    expect(component.container.textContent).toBe("-");
  });
});
