import { describe, expect, it, vi } from "vitest";

import { store } from "@/shared/stores";

import { getRelationships } from "@/entities/nodes/relationships/domain/get-relationships/get-relationships";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { RelationshipHierarchicalComboboxList } from "@/entities/nodes/relationships/ui/relationship-hierarchical-combobox-list";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../tests/components/render";
import { generateGenericSchema, generateNodeSchema } from "../../../../../tests/fake/schema";

vi.mock("@/entities/nodes/relationships/domain/get-relationships/get-relationships");

describe("RelationshipHierarchicalComboboxList", () => {
  const hierarchyGenericSchema = generateGenericSchema({ hierarchical: true });
  const rootSchema = generateNodeSchema({
    kind: "Root",
    parent: null,
    hierarchy: hierarchyGenericSchema.kind,
    children: "Parent",
  });
  const parentSchema = generateNodeSchema({
    kind: "Parent",
    parent: rootSchema.kind,
    hierarchy: hierarchyGenericSchema.kind,
    children: "Child",
  });
  const childSchema = generateNodeSchema({
    kind: "Child",
    parent: parentSchema.kind,
    hierarchy: hierarchyGenericSchema.kind,
  });

  const relationships: RelationshipNode[] = [
    {
      id: "test-id-1",
      display_label: "Test Relationship 1",
      __typename: rootSchema.kind,
    },
    {
      id: "test-id-2",
      display_label: "Test Relationship 2",
      __typename: rootSchema.kind,
    },
  ];

  const parentRelationships: RelationshipNode[] = [
    {
      id: "parent-1",
      display_label: "Parent Relationship 1",
      __typename: parentSchema.kind,
    },
    {
      id: "parent-2",
      display_label: "Parent Relationship 2",
      __typename: parentSchema.kind,
    },
  ];

  const childRelationships: RelationshipNode[] = [
    {
      id: "child-1",
      display_label: "Child Relationship 1",
      __typename: childSchema.kind,
    },
    {
      id: "child-2",
      display_label: "Child Relationship 2",
      __typename: childSchema.kind,
    },
  ];

  beforeEach(() => {
    store.set(genericSchemasAtom, [hierarchyGenericSchema]);
    store.set(nodeSchemasAtom, [rootSchema, parentSchema, childSchema]);
    vi.mocked(getRelationships).mockResolvedValue([]);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("displays message when schema is not hierarchical", async () => {
    // GIVEN
    const notHierarchicalSchema = generateNodeSchema();

    // WHEN
    const component = await render(
      <RelationshipHierarchicalComboboxList peer={notHierarchicalSchema.kind} onSelect={vi.fn()} />
    );

    // THEN
    await expect
      .element(component.getByText("This schema is not a node with hierarchy"))
      .toBeVisible();
  });

  it("displays message when no relationships are found", async () => {
    // GIVEN
    vi.mocked(getRelationships).mockResolvedValue([]);

    // WHEN
    const component = await render(
      <RelationshipHierarchicalComboboxList peer={childSchema.kind} onSelect={vi.fn()} />
    );

    // THEN
    await expect.element(component.getByText("No results found")).toBeVisible();
  });

  it("displays relationships of root schema", async () => {
    // GIVEN
    vi.mocked(getRelationships).mockResolvedValue(relationships);

    // WHEN
    const component = await render(
      <RelationshipHierarchicalComboboxList peer={rootSchema.kind} onSelect={vi.fn()} />
    );

    // THEN
    const firstOption = component.getByRole("option", { name: relationships[0]!.display_label });
    await expect.element(firstOption).toBeVisible();
    await expect.element(firstOption).toHaveAttribute("aria-selected", "true");

    const secondOption = component.getByRole("option", { name: relationships[1]!.display_label });
    await expect.element(secondOption).toBeVisible();
    await expect.element(secondOption).toHaveAttribute("aria-selected", "false");
  });

  it("calls onSelect when a relationship is selected", async () => {
    // GIVEN
    vi.mocked(getRelationships).mockResolvedValue(relationships);
    const onSelect = vi.fn();
    const component = await render(
      <RelationshipHierarchicalComboboxList peer={rootSchema.kind} onSelect={onSelect} />
    );

    // WHEN
    await component.getByRole("option", { name: relationships[1]!.display_label }).click();

    // THEN
    expect(onSelect).toHaveBeenCalledOnce();
    expect(onSelect).toHaveBeenCalledWith(relationships[1]);
  });

  it("navigates from parent to direct child relationships and selects child", async () => {
    // GIVEN
    vi.mocked(getRelationships)
      .mockResolvedValueOnce(parentRelationships)
      .mockResolvedValueOnce(childRelationships);
    const onSelect = vi.fn();
    const component = await render(
      <RelationshipHierarchicalComboboxList peer={childSchema.kind} onSelect={onSelect} />
    );

    // WHEN
    await component.getByRole("option", { name: parentRelationships[0]!.display_label }).click();
    expect(onSelect).not.toBeCalled();
    await component.getByRole("option", { name: childRelationships[1]!.display_label }).click();

    // THEN
    expect(onSelect).toHaveBeenCalledOnce();
    expect(onSelect).toHaveBeenCalledWith(childRelationships[1]);
  });

  it("navigates through multiple levels of nested relationships", async () => {
    // GIVEN
    vi.mocked(getRelationships)
      .mockResolvedValueOnce(relationships)
      .mockResolvedValueOnce(parentRelationships)
      .mockResolvedValueOnce(childRelationships);
    const onSelect = vi.fn();
    const component = await render(
      <RelationshipHierarchicalComboboxList peer={childSchema.kind} onSelect={onSelect} />
    );

    // WHEN
    await component.getByRole("option", { name: relationships[0]!.display_label }).click();
    expect(onSelect).not.toBeCalled();

    await component.getByRole("option", { name: parentRelationships[0]!.display_label }).click();
    expect(onSelect).not.toBeCalled();

    await component.getByRole("option", { name: childRelationships[1]!.display_label }).click();

    // THEN
    expect(onSelect).toHaveBeenCalledOnce();
    expect(onSelect).toHaveBeenCalledWith(childRelationships[1]);
  });

  it("displays load more button when there are more results", async () => {
    // GIVEN
    const manyRelationships = Array.from({ length: 20 }, (_, i) => ({
      id: `test-id-${i}`,
      display_label: `Test Relationship ${i}`,
      __typename: rootSchema.kind,
    }));
    vi.mocked(getRelationships).mockResolvedValue(manyRelationships);

    // WHEN
    const component = await render(
      <RelationshipHierarchicalComboboxList peer={rootSchema.kind} onSelect={vi.fn()} />
    );

    // THEN
    await expect.element(component.getByRole("option", { name: "Load more" })).toBeVisible();
  });

  it("shows scrollbar when there are many options", async () => {
    // GIVEN
    const manyRelationships = Array.from({ length: 30 }, (_, i) => ({
      id: `test-id-${i}`,
      display_label: `Test Relationship ${i}`,
      __typename: rootSchema.kind,
    }));
    vi.mocked(getRelationships).mockResolvedValue(manyRelationships);

    // WHEN
    const component = await render(
      <RelationshipHierarchicalComboboxList peer={rootSchema.kind} onSelect={vi.fn()} />
    );

    // THEN
    const listbox = component.getByRole("listbox");
    expect(listbox.element().scrollHeight).toBeGreaterThan(listbox.element().clientHeight);
  });
});
