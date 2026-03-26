import { describe, expect, it } from "vitest";

import type { NodeObjectWithMetadata } from "@/entities/nodes/types";

import { render } from "../../../../../../../tests/components/render";
import {
  generateNodeAttributeWithMetadata,
  generateRelationshipNodeWithMetadata,
} from "../../../../../../../tests/fake/node";
import { generatePermission } from "../../../../../../../tests/fake/permission";
import {
  generateAttributeSchema,
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../../tests/fake/schema";
import { ObjectDataDisplay } from "./object-data-display";

const permission = generatePermission();

describe("ObjectDataDisplay - showExtra filtering", () => {
  it("hides fields with display 'extra' by default", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({
          name: "name",
          label: "Name",
          display: "default",
          order_weight: 1000,
        }),
        generateAttributeSchema({
          name: "description",
          label: "Description",
          display: "extra",
          order_weight: 2000,
        }),
      ],
      relationships: [],
    });

    const objectData: NodeObjectWithMetadata = {
      id: "test-1",
      display_label: "Test",
      __typename: "BuiltinTag",
      name: generateNodeAttributeWithMetadata({ value: "test" }),
      description: generateNodeAttributeWithMetadata({ value: "a desc" }),
    };

    // WHEN
    const component = await render(
      <ObjectDataDisplay objectSchema={schema} objectData={objectData} permission={permission} />
    );

    // THEN
    await expect.element(component.getByText("Name")).toBeVisible();
    await expect.element(component.baseElement).not.toHaveTextContent("Description");
  });

  it("shows fields with display 'extra' when showExtra is true", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({
          name: "name",
          label: "Name",
          display: "default",
          order_weight: 1000,
        }),
        generateAttributeSchema({
          name: "description",
          label: "Description",
          display: "extra",
          order_weight: 2000,
        }),
      ],
      relationships: [],
    });

    const objectData: NodeObjectWithMetadata = {
      id: "test-1",
      display_label: "Test",
      __typename: "BuiltinTag",
      name: generateNodeAttributeWithMetadata({ value: "test" }),
      description: generateNodeAttributeWithMetadata({ value: "a desc" }),
    };

    // WHEN
    const component = await render(
      <ObjectDataDisplay
        objectSchema={schema}
        objectData={objectData}
        permission={permission}
        showExtra
      />
    );

    // THEN
    await expect.element(component.getByText("Name")).toBeVisible();
    await expect.element(component.getByText("Description")).toBeVisible();
  });

  it("shows all default fields regardless of showExtra", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({
          name: "name",
          label: "Name",
          display: "default",
          order_weight: 1000,
        }),
        generateAttributeSchema({
          name: "description",
          label: "Description",
          display: "default",
          order_weight: 2000,
        }),
      ],
      relationships: [],
    });

    const objectData: NodeObjectWithMetadata = {
      id: "test-1",
      display_label: "Test",
      __typename: "BuiltinTag",
      name: generateNodeAttributeWithMetadata({ value: "test" }),
      description: generateNodeAttributeWithMetadata({ value: "a desc" }),
    };

    // WHEN
    const component = await render(
      <ObjectDataDisplay objectSchema={schema} objectData={objectData} permission={permission} />
    );

    // THEN
    await expect.element(component.getByText("Name")).toBeVisible();
    await expect.element(component.getByText("Description")).toBeVisible();
  });

  it("renders nothing when all fields are extra and showExtra is false", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({
          name: "name",
          label: "Name",
          display: "extra",
          order_weight: 1000,
        }),
      ],
      relationships: [],
    });

    const objectData: NodeObjectWithMetadata = {
      id: "test-1",
      display_label: "Test",
      __typename: "BuiltinTag",
      name: generateNodeAttributeWithMetadata({ value: "test" }),
    };

    // WHEN
    const component = await render(
      <ObjectDataDisplay objectSchema={schema} objectData={objectData} permission={permission} />
    );

    // THEN
    await expect.element(component.baseElement).not.toHaveTextContent("Name");
  });

  it("renders nothing when schema has no attributes or relationships", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [],
      relationships: [],
    });

    const objectData: NodeObjectWithMetadata = {
      id: "test-1",
      display_label: "Test",
      __typename: "BuiltinTag",
    };

    // WHEN
    const component = await render(
      <ObjectDataDisplay objectSchema={schema} objectData={objectData} permission={permission} />
    );

    // THEN
    await expect.element(component.baseElement).not.toHaveTextContent("Name");
  });

  it("hides extra relationships by default", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({
          name: "name",
          label: "Name",
          display: "default",
          order_weight: 1000,
        }),
      ],
      relationships: [
        generateRelationshipSchema({
          name: "device",
          label: "Device",
          peer: "InfraDevice",
          kind: "Parent",
          cardinality: "one",
          display: "extra",
          order_weight: 2000,
        }),
      ],
    });

    const objectData: NodeObjectWithMetadata = {
      id: "test-1",
      display_label: "Test",
      __typename: "BuiltinTag",
      name: generateNodeAttributeWithMetadata({ value: "test" }),
      device: generateRelationshipNodeWithMetadata({
        node: { id: "dev-1", display_label: "Device 1", __typename: "InfraDevice" },
      }),
    };

    // WHEN
    const component = await render(
      <ObjectDataDisplay objectSchema={schema} objectData={objectData} permission={permission} />
    );

    // THEN
    await expect.element(component.getByText("Name")).toBeVisible();
    await expect.element(component.baseElement).not.toHaveTextContent("Device");
  });

  it("shows extra relationships when showExtra is true", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({
          name: "name",
          label: "Name",
          display: "default",
          order_weight: 1000,
        }),
      ],
      relationships: [
        generateRelationshipSchema({
          name: "device",
          label: "Device",
          peer: "InfraDevice",
          kind: "Parent",
          cardinality: "one",
          display: "extra",
          order_weight: 2000,
        }),
      ],
    });

    const objectData: NodeObjectWithMetadata = {
      id: "test-1",
      display_label: "Test",
      __typename: "BuiltinTag",
      name: generateNodeAttributeWithMetadata({ value: "test" }),
      device: generateRelationshipNodeWithMetadata({
        node: { id: "dev-1", display_label: "Device 1", __typename: "InfraDevice" },
      }),
    };

    // WHEN
    const component = await render(
      <ObjectDataDisplay
        objectSchema={schema}
        objectData={objectData}
        permission={permission}
        showExtra
      />
    );

    // THEN
    await expect.element(component.getByText("Name")).toBeVisible();
    await expect.element(component.getByText("Device")).toBeVisible();
  });

  it("filters only extra fields in a mix of default and extra", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({
          name: "name",
          label: "Name",
          display: "default",
          order_weight: 1000,
        }),
        generateAttributeSchema({
          name: "description",
          label: "Description",
          display: "extra",
          order_weight: 2000,
        }),
        generateAttributeSchema({
          name: "status",
          label: "Status",
          display: "default",
          order_weight: 3000,
        }),
      ],
      relationships: [],
    });

    const objectData: NodeObjectWithMetadata = {
      id: "test-1",
      display_label: "Test",
      __typename: "BuiltinTag",
      name: generateNodeAttributeWithMetadata({ value: "test" }),
      description: generateNodeAttributeWithMetadata({ value: "a desc" }),
      status: generateNodeAttributeWithMetadata({ value: "active" }),
    };

    // WHEN
    const component = await render(
      <ObjectDataDisplay objectSchema={schema} objectData={objectData} permission={permission} />
    );

    // THEN
    await expect.element(component.getByText("Name")).toBeVisible();
    await expect.element(component.getByText("Status")).toBeVisible();
    await expect.element(component.baseElement).not.toHaveTextContent("Description");
  });

  it("shows eye icon on extra attribute rows when showExtra is true", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({
          name: "name",
          label: "Name",
          display: "default",
          order_weight: 1000,
        }),
        generateAttributeSchema({
          name: "description",
          label: "Description",
          display: "extra",
          order_weight: 2000,
        }),
      ],
      relationships: [],
    });

    const objectData: NodeObjectWithMetadata = {
      id: "test-1",
      display_label: "Test",
      __typename: "BuiltinTag",
      name: generateNodeAttributeWithMetadata({ value: "test" }),
      description: generateNodeAttributeWithMetadata({ value: "a desc" }),
    };

    // WHEN
    const component = await render(
      <ObjectDataDisplay
        objectSchema={schema}
        objectData={objectData}
        permission={permission}
        showExtra
      />
    );

    // THEN
    await expect.element(component.getByTestId("extra-field-indicator")).toBeVisible();
  });

  it("shows eye icon on extra relationship rows when showExtra is true", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({
          name: "name",
          label: "Name",
          display: "default",
          order_weight: 1000,
        }),
      ],
      relationships: [
        generateRelationshipSchema({
          name: "device",
          label: "Device",
          peer: "InfraDevice",
          kind: "Parent",
          cardinality: "one",
          display: "extra",
          order_weight: 2000,
        }),
      ],
    });

    const objectData: NodeObjectWithMetadata = {
      id: "test-1",
      display_label: "Test",
      __typename: "BuiltinTag",
      name: generateNodeAttributeWithMetadata({ value: "test" }),
      device: generateRelationshipNodeWithMetadata({
        node: { id: "dev-1", display_label: "Device 1", __typename: "InfraDevice" },
      }),
    };

    // WHEN
    const component = await render(
      <ObjectDataDisplay
        objectSchema={schema}
        objectData={objectData}
        permission={permission}
        showExtra
      />
    );

    // THEN
    await expect.element(component.getByTestId("extra-field-indicator")).toBeVisible();
  });

  it("does not show eye icon on default-only fields when showExtra is true", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({
          name: "name",
          label: "Name",
          display: "default",
          order_weight: 1000,
        }),
      ],
      relationships: [],
    });

    const objectData: NodeObjectWithMetadata = {
      id: "test-1",
      display_label: "Test",
      __typename: "BuiltinTag",
      name: generateNodeAttributeWithMetadata({ value: "test" }),
    };

    // WHEN
    const component = await render(
      <ObjectDataDisplay
        objectSchema={schema}
        objectData={objectData}
        permission={permission}
        showExtra
      />
    );

    // THEN
    expect(component.getByTestId("extra-field-indicator").query()).toBeNull();
  });

  it("does not show eye icon when showExtra is false", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({
          name: "name",
          label: "Name",
          display: "default",
          order_weight: 1000,
        }),
        generateAttributeSchema({
          name: "description",
          label: "Description",
          display: "extra",
          order_weight: 2000,
        }),
      ],
      relationships: [],
    });

    const objectData: NodeObjectWithMetadata = {
      id: "test-1",
      display_label: "Test",
      __typename: "BuiltinTag",
      name: generateNodeAttributeWithMetadata({ value: "test" }),
      description: generateNodeAttributeWithMetadata({ value: "a desc" }),
    };

    // WHEN
    const component = await render(
      <ObjectDataDisplay objectSchema={schema} objectData={objectData} permission={permission} />
    );

    // THEN
    expect(component.getByTestId("extra-field-indicator").query()).toBeNull();
  });

  it("skips fields that have no corresponding data in objectData", async () => {
    // GIVEN
    const schema = generateNodeSchema({
      attributes: [
        generateAttributeSchema({
          name: "name",
          label: "Name",
          display: "default",
          order_weight: 1000,
        }),
        generateAttributeSchema({
          name: "missing_field",
          label: "Missing",
          display: "default",
          order_weight: 2000,
        }),
      ],
      relationships: [],
    });

    const objectData: NodeObjectWithMetadata = {
      id: "test-1",
      display_label: "Test",
      __typename: "BuiltinTag",
      name: generateNodeAttributeWithMetadata({ value: "test" }),
    };

    // WHEN
    const component = await render(
      <ObjectDataDisplay objectSchema={schema} objectData={objectData} permission={permission} />
    );

    // THEN
    await expect.element(component.getByText("Name")).toBeVisible();
    await expect.element(component.baseElement).not.toHaveTextContent("Missing");
  });
});
