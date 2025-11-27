import { describe, expect, test } from "vitest";

import { render } from "../../../../tests/components/render";
import { generateAttributeSchema, generateNodeSchema } from "../../../../tests/fake/schema";
import { SchemaViewer } from "./schema-viewer";

describe("SchemaViewer Component", () => {
  test("displays node description", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      name: "Node",
      namespace: "Test",
      description: "Test Node description",
    });

    const component = await render(<SchemaViewer schema={schema} onClose={() => {}} />);

    // THEN
    await expect
      .element(component.getByRole("paragraph").getByText("Test Node description"))
      .toBeVisible();
  });

  test("displays text attribute details", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      name: "Node",
      namespace: "Test",
      attributes: [
        generateAttributeSchema({
          id: "random-id",
          name: "attribute",
          label: "attribute",
          kind: "Text",
          optional: false,
          read_only: false,
          computed_attribute: {
            kind: "Jinja2",
            jinja2_template: "test",
          },
          parameters: {
            regex: "test-regex",
            state: "present",
            min_length: 1,
            max_length: 10,
          },
        }),
      ],
    });

    const component = await render(<SchemaViewer schema={schema} onClose={() => {}} />);

    // WHEN
    await component.getByText("Attributes").click();
    await component.getByText("attribute Text").click();

    // THEN
    await expect.element(component.getByText("random-id")).toBeVisible();
    await expect.element(component.getByText("CoreTransformJinja2")).toBeVisible();
    await expect.element(component.getByText("test-regex")).toBeVisible();
    await expect.element(component.getByText("Min length1")).toBeVisible();
    await expect.element(component.getByText("Max length10")).toBeVisible();
  });

  test("displays number pool attribute details", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      name: "Node",
      namespace: "Test",
      attributes: [
        generateAttributeSchema({
          id: "random-id",
          name: "attribute",
          label: "Attribute",
          kind: "NumberPool",
          optional: false,
          read_only: false,
          parameters: {
            state: "present",
            number_pool_id: "random-pool-id",
            start_range: 10,
            end_range: 100,
          },
        }),
      ],
    });

    const component = await render(<SchemaViewer schema={schema} onClose={() => {}} />);

    // WHEN
    await component.getByText("Attributes").click();
    await component.getByText("Attribute NumberPool").click();

    // THEN
    await expect.element(component.getByText("random-pool-id")).toBeVisible();
    await expect.element(component.getByText("Number pool")).toBeVisible();
    await expect.element(component.getByText("Start range10")).toBeVisible();
    await expect.element(component.getByText("End range100")).toBeVisible();
  });

  test("displays number attribute details", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      name: "Node",
      namespace: "Test",
      attributes: [
        generateAttributeSchema({
          id: "random-id",
          name: "attribute",
          label: "Attribute",
          kind: "Number",
          optional: false,
          read_only: false,
          parameters: {
            state: "present",
            min_value: -10,
            max_value: 100,
            excluded_values: "1,2,3",
          },
        }),
      ],
    });

    const component = await render(<SchemaViewer schema={schema} onClose={() => {}} />);

    // WHEN
    await component.getByText("Attributes").click();
    await component.getByText("Attribute Number").click();

    // THEN
    await expect.element(component.getByText("Min value-10")).toBeVisible();
    await expect.element(component.getByText("Max value100")).toBeVisible();
    await expect.element(component.getByText("Excluded values1,2,3")).toBeVisible();
  });

  test("displays Jinja2 template details", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      name: "Node",
      namespace: "Test",
      attributes: [
        generateAttributeSchema({
          id: "random-id",
          name: "attribute",
          label: "attribute",
          kind: "Text",
          optional: false,
          read_only: false,
          computed_attribute: {
            kind: "Jinja2",
            jinja2_template: "{{ name__value | upper }}",
          },
        }),
      ],
    });

    const component = await render(<SchemaViewer schema={schema} onClose={() => {}} />);

    // WHEN
    await component.getByText("Attributes").click();
    await component.getByText("attribute Text").click();
    await component.getByTestId("jinja2-transform-button").click();

    // THEN
    await expect.element(component.getByText("Jinja2 Template")).toBeVisible();
    await expect.element(component.getByText("{{ name__value | upper }}").first()).toBeVisible();
  });

  test("displays Python transform details", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      name: "Node",
      namespace: "Test",
      attributes: [
        generateAttributeSchema({
          id: "random-id",
          name: "attribute",
          label: "attribute",
          kind: "Text",
          optional: false,
          read_only: false,
          computed_attribute: {
            kind: "TransformPython",
            transform: "test-transform",
          },
        }),
      ],
    });

    const component = await render(<SchemaViewer schema={schema} onClose={() => {}} />);

    // WHEN
    await component.getByText("Attributes").click();
    await component.getByText("attribute Text").click();

    // THEN
    await expect.element(component.getByText("CoreTransformPython")).toBeVisible();
    await expect.element(component.getByText("test-transform").first()).toBeVisible();
  });
});
