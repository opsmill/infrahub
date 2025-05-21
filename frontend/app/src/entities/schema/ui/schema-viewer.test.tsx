import { describe, expect, test } from "vitest";
import { render } from "../../../../tests/components/render";
import { generateNodeSchema } from "../../../../tests/fake/schema";
import { SchemaViewer } from "./schema-viewer";

describe("Schema Visualizer Component", () => {
  test("renders viewer correctly", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      name: "Node",
      namespace: "Test",
      description: "Test Node description",
    });

    const component = render(<SchemaViewer schema={schema} onClose={function (): void {}} />);

    // THEN
    await expect
      .element(component.getByRole("paragraph").getByText("Test Node description"))
      .toBeVisible();
  });

  test("renders attributes correctly", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      name: "Node",
      namespace: "Test",
      attributes: [
        {
          id: "random-id",
          name: "attribute",
          kind: "Text",
          optional: false,
          read_only: false,
          computed_attribute: {
            kind: "Jinja2",
            jinja2_template: "test",
          },
          parameters: {
            regex: "test-regex",
            min_length: 1,
            max_length: 10,
          },
        },
      ],
    });

    const component = render(<SchemaViewer schema={schema} onClose={function (): void {}} />);

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

  test("renders jinja template correctly", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      name: "Node",
      namespace: "Test",
      attributes: [
        {
          id: "random-id",
          name: "attribute",
          kind: "Text",
          optional: false,
          read_only: false,
          computed_attribute: {
            kind: "Jinja2",
            jinja2_template: "{{ name__value | upper }}",
          },
        },
      ],
    });

    const component = render(<SchemaViewer schema={schema} onClose={function (): void {}} />);

    // WHEN
    await component.getByText("Attributes").click();
    await component.getByText("attribute Text").click();
    await component.getByTestId("jinja2-transform-button").click();

    // THEN
    await expect.element(component.getByText("Jinja2 Template")).toBeVisible();
    await expect.element(component.getByText("{{ name__value | upper }}").first()).toBeVisible();
  });

  test("renders json transform correctly", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      name: "Node",
      namespace: "Test",
      attributes: [
        {
          id: "random-id",
          name: "attribute",
          kind: "Text",
          optional: false,
          read_only: false,
          computed_attribute: {
            kind: "TransformPython",
            transform: "test-transform",
          },
        },
      ],
    });

    const component = render(<SchemaViewer schema={schema} onClose={function (): void {}} />);

    // WHEN
    await component.getByText("Attributes").click();
    await component.getByText("attribute Text").click();

    // THEN
    await expect.element(component.getByText("CoreTransformPython")).toBeVisible();
    await expect.element(component.getByText("test-transform").first()).toBeVisible();
  });
});
