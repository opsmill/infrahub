import { describe, expect, test } from "vitest";

import type { NodeAttribute } from "@/entities/nodes/object/domain/model/node";

import { render } from "../../../../../../../tests/components/render";
import { generateAttributeSchema } from "../../../../../../../tests/fake/schema";
import { TableAttributeCell } from "./table-attribute-cell";

const attribute = (value: unknown) => ({ value }) as NodeAttribute;

const uplinks = Array.from({ length: 30 }, (_, index) => `Ethernet1/${index + 1}`);

describe("TableAttributeCell", () => {
  test("opens the element of a one-element List", async () => {
    // GIVEN
    const schema = generateAttributeSchema({ name: "uplinks", kind: "List", label: "Uplinks" });
    const component = await render(
      <TableAttributeCell attributeSchema={schema} attributeData={attribute(["mgmt0"])} />
    );

    // WHEN
    await component.getByRole("button", { name: "View all 1 element of Uplinks" }).click();

    // THEN
    await expect
      .element(component.getByRole("dialog").getByText("mgmt0", { exact: true }))
      .toBeInTheDocument();
  });

  test("shows a JSON value holding size 0 rather than a dash", async () => {
    // GIVEN
    const schema = generateAttributeSchema({ name: "disk", kind: "JSON", label: "Disk" });

    // WHEN
    const component = await render(
      <TableAttributeCell attributeSchema={schema} attributeData={attribute({ size: 0 })} />
    );

    // THEN
    await expect.element(component.getByRole("button", { name: "View Disk JSON" })).toBeVisible();
  });

  test("shows no filter in the dialog of a 12-element List", async () => {
    // GIVEN
    const schema = generateAttributeSchema({ name: "uplinks", kind: "List", label: "Uplinks" });
    const component = await render(
      <TableAttributeCell
        attributeSchema={schema}
        attributeData={attribute(uplinks.slice(0, 12))}
      />
    );

    // WHEN
    await component.getByRole("button", { name: "View all 12 elements of Uplinks" }).click();

    // THEN
    await expect
      .element(component.getByRole("dialog").getByText("Ethernet1/12", { exact: true }))
      .toBeInTheDocument();
    expect(component.getByRole("textbox", { name: "Filter elements" }).query()).toBeNull();
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
        attributeData={attribute({ bgp: { asn: 65_101 } })}
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
