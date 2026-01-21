import { describe, expect, test } from "vitest";

import { render } from "../../../../tests/components/render";
import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../tests/fake/schema";
import { SchemaViewerModal } from "./schema-viewer-modal";

describe("SchemaViewerModal Component", () => {
  test("renders modal with schema information", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      name: "Device",
      namespace: "Infra",
      label: "Device",
      description: "A network device",
    });

    const component = await render(<SchemaViewerModal schema={schema} isOpen />);

    // THEN
    await expect.element(component.getByRole("dialog")).toBeVisible();
    await expect.element(component.getByRole("heading", { name: "Device" })).toBeVisible();
    await expect.element(component.getByRole("paragraph")).toBeVisible();
    await expect.element(component.getByTestId("schema-viewer")).toBeVisible();
  });

  test("opens attributes tab by default when defaultTab is 'attributes'", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      name: "Device",
      namespace: "Infra",
      attributes: [
        generateAttributeSchema({
          id: "attr-1",
          name: "hostname",
          label: "Hostname",
          kind: "Text",
        }),
      ],
    });

    const component = await render(
      <SchemaViewerModal schema={schema} defaultTab="attributes" isOpen />
    );

    // THEN
    await expect.element(component.getByText("Hostname Text")).toBeVisible();
  });

  test("opens relationships tab by default when defaultTab is 'relationships'", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      name: "Device",
      namespace: "Infra",
      relationships: [
        generateRelationshipSchema({
          id: "rel-1",
          name: "interfaces",
          label: "Interfaces",
          peer: "InfraInterface",
          cardinality: "many",
        }),
      ],
    });

    const component = await render(
      <SchemaViewerModal schema={schema} defaultTab="relationships" isOpen />
    );

    // THEN
    await expect.element(component.getByText("Interfaces")).toBeVisible();
    await expect.element(component.getByText("InfraInterface")).toBeVisible();
  });

  test("expands target attribute when targetField matches attribute name", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      name: "Device",
      namespace: "Infra",
      attributes: [
        generateAttributeSchema({
          id: "attr-1",
          name: "hostname",
          label: "Hostname",
          kind: "Text",
        }),
        generateAttributeSchema({
          id: "attr-2",
          name: "description",
          label: "Description",
          kind: "Text",
        }),
      ],
    });

    const component = await render(
      <SchemaViewerModal schema={schema} defaultTab="attributes" targetField="hostname" isOpen />
    );

    // THEN - the target attribute should be expanded showing its details
    await expect.element(component.getByText("attr-1")).toBeVisible();
  });

  test("expands target relationship when targetField matches relationship name", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      name: "Device",
      namespace: "Infra",
      relationships: [
        generateRelationshipSchema({
          id: "rel-1",
          name: "interfaces",
          label: "Interfaces",
          peer: "InfraInterface",
        }),
        generateRelationshipSchema({
          id: "rel-2",
          name: "location",
          label: "Location",
          peer: "LocationSite",
        }),
      ],
    });

    const component = await render(
      <SchemaViewerModal
        schema={schema}
        defaultTab="relationships"
        targetField="interfaces"
        isOpen
      />
    );

    // THEN - the target relationship should be expanded showing its details
    await expect.element(component.getByText("rel-1")).toBeVisible();
  });
});
