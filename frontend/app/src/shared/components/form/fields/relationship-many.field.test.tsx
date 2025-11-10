import { describe, expect, test, vi } from "vitest";

import type { DynamicRelationshipFieldProps } from "@/shared/components/form/type";
import { store } from "@/shared/stores";

import { getRelationships } from "@/entities/nodes/relationships/domain/get-relationships/get-relationships";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { TestForm } from "../../../../../tests/components/form.story";
import { render } from "../../../../../tests/components/render";
import { generateNodeSchema, generateRelationshipSchema } from "../../../../../tests/fake/schema";
import RelationshipManyField from "./relationships/relationship-many.field";

vi.mock("@/entities/nodes/relationships/domain/get-relationships/get-relationships");

describe("RelationshipMany - Field", () => {
  const relationshipSchema = generateRelationshipSchema();
  const objectSchema = generateNodeSchema({
    relationships: [relationshipSchema],
  });

  beforeEach(() => {
    store.set(nodeSchemasAtom, [objectSchema]);

    const mockNodes: RelationshipNode[] = [
      { id: "1", display_label: "Node 1", __typename: "TestNode" },
      { id: "2", display_label: "Node 2", __typename: "TestNode" },
      { id: "3", display_label: "Node 3", __typename: "TestNode" },
    ];
    vi.mocked(getRelationships).mockResolvedValue(mockNodes);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  const defaultProps: Omit<DynamicRelationshipFieldProps, "type"> = {
    name: "testField",
    label: "Test Field",
    peer: "TestNode",
    schema: objectSchema,
    relationship: relationshipSchema,
  };

  test("renders with default props", async () => {
    // GIVEN
    const component = render(
      <TestForm>
        <RelationshipManyField {...defaultProps} />
      </TestForm>
    );

    // THEN
    await expect.element(component.getByLabelText("Test Field")).toBeVisible();
    await expect.poll(() => component.getByText("*").query()).toBeNull();
    await expect.poll(() => component.getByRole("button", { name: "?" }).query()).toBeNull();
  });

  test("renders with description", async () => {
    // GIVEN
    const component = render(
      <TestForm>
        <RelationshipManyField {...defaultProps} description="Test description" />
      </TestForm>
    );

    // THEN
    await expect.element(component.getByRole("button", { name: "?" })).toBeVisible();
  });

  test("renders with unique indicator when unique is true", async () => {
    // GIVEN
    const component = render(
      <TestForm>
        <RelationshipManyField {...defaultProps} unique />
      </TestForm>
    );

    // THEN
    await expect.element(component.getByText("must be unique")).toBeVisible();
  });

  test("renders with required indicator and required the value", async () => {
    // GIVEN
    const component = render(
      <TestForm>
        <RelationshipManyField {...defaultProps} rules={{ required: true }} />
      </TestForm>
    );

    // THEN
    await expect.element(component.getByText("Test Field *")).toBeVisible();
  });
});
