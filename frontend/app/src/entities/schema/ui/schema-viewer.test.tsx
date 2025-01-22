import queryString from "query-string";
import { QueryParamProvider } from "use-query-params";
import { ReactRouter6Adapter } from "use-query-params/adapters/react-router-6";
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

    const component = render(
      <QueryParamProvider
        adapter={ReactRouter6Adapter}
        options={{
          searchStringToObject: queryString.parse,
          objectToSearchString: queryString.stringify,
        }}
      >
        <SchemaViewer schema={schema} onClose={function (): void {}} />
      </QueryParamProvider>
    );

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
            jinja2_template: "",
          },
        },
      ],
    });

    const component = render(
      <QueryParamProvider
        adapter={ReactRouter6Adapter}
        options={{
          searchStringToObject: queryString.parse,
          objectToSearchString: queryString.stringify,
        }}
      >
        <SchemaViewer schema={schema} onClose={function (): void {}} />
      </QueryParamProvider>
    );

    // WHEN
    await component.getByText("Attributes").click();
    await component.getByText("attribute Text").click();

    // THEN
    await expect.element(component.getByText("random-id")).toBeVisible();
    await expect.element(component.getByText("CoreTransformJinja2")).toBeVisible();
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

    const component = render(
      <QueryParamProvider
        adapter={ReactRouter6Adapter}
        options={{
          searchStringToObject: queryString.parse,
          objectToSearchString: queryString.stringify,
        }}
      >
        <SchemaViewer schema={schema} onClose={function (): void {}} />
      </QueryParamProvider>
    );

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

    const component = render(
      <QueryParamProvider
        adapter={ReactRouter6Adapter}
        options={{
          searchStringToObject: queryString.parse,
          objectToSearchString: queryString.stringify,
        }}
      >
        <SchemaViewer schema={schema} onClose={function (): void {}} />
      </QueryParamProvider>
    );

    // WHEN
    await component.getByText("Attributes").click();
    await component.getByText("attribute Text").click();

    // THEN
    await expect.element(component.getByText("CoreTransformPython")).toBeVisible();
    await expect.element(component.getByText("test-transform").first()).toBeVisible();
  });
});
