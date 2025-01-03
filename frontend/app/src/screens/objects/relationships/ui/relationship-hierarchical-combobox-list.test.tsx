import { useSchema } from "@/hooks/useSchema";
import { getRelationships } from "@/screens/objects/relationships/domain/get-relationships/get-relationships";
import { RelationshipNode } from "@/screens/objects/relationships/domain/types";
import { RelationshipHierarchicalComboboxList } from "@/screens/objects/relationships/ui/relationship-hierarchical-combobox-list";
import { describe, expect, it, vi } from "vitest";
import { render } from "../../../../../tests/components/render";
import { generateGenericSchema, generateNodeSchema } from "../../../../../tests/fake/schema";

vi.mock("@/hooks/useSchema");
vi.mock("@/screens/objects/relationships/domain/get-relationships/get-relationships");

describe("RelationshipComboboxList", () => {
  const hierarchyGenericSchema = generateGenericSchema({ hierarchical: true });
  const rootSchema = generateNodeSchema({
    kind: "Root",
    parent: null,
    hierarchy: hierarchyGenericSchema.kind,
  });
  const parentSchema = generateNodeSchema({
    kind: "Parent",
    parent: rootSchema.kind,
    hierarchy: hierarchyGenericSchema.kind,
  });
  const childSchema = generateNodeSchema({
    kind: "Child",
    parent: parentSchema.kind,
    hierarchy: hierarchyGenericSchema.kind,
  });

  it("displays message when schema is not hierarchical", async () => {
    // GIVEN
    const notHierarchicalSchema = generateNodeSchema();
    vi.mocked(useSchema).mockReturnValue({
      schema: notHierarchicalSchema,
      isNode: true,
      isGeneric: false,
      isProfile: false,
    });

    // WHEN
    const component = render(
      <RelationshipHierarchicalComboboxList peer={notHierarchicalSchema.kind} onSelect={() => {}} />
    );

    // THEN
    await expect
      .element(component.getByText("This schema is not a node with hierarchy"))
      .toBeVisible();
  });

  it("displays message when no relationships are found", async () => {
    // GIVEN
    vi.mocked(getRelationships).mockResolvedValue([]);
    vi.mocked(useSchema).mockReturnValue({
      schema: childSchema,
      isNode: true,
      isGeneric: false,
      isProfile: false,
    });
    const component = render(
      <RelationshipHierarchicalComboboxList peer={childSchema.kind} onSelect={() => {}} />
    );

    // THEN
    await expect.element(component.getByText("No results found")).toBeVisible();
  });

  it("displays relationships when available", async () => {
    // GIVEN
    const relationships: Array<RelationshipNode> = [
      {
        id: "test-id-1",
        display_label: "Test Relationship 1",
        __typename: childSchema.kind,
      },
      {
        id: "test-id-2",
        display_label: "Test Relationship 2",
        __typename: childSchema.kind,
      },
    ];
    vi.mocked(getRelationships).mockResolvedValue(relationships);
    vi.mocked(useSchema).mockReturnValue({
      schema: childSchema,
      isNode: true,
      isGeneric: false,
      isProfile: false,
    });

    // WHEN
    const component = render(
      <RelationshipHierarchicalComboboxList peer={childSchema.kind} onSelect={() => {}} />
    );

    // THEN
    const firstOption = component.getByRole("option", { name: relationships[0]?.display_label });
    await expect.element(firstOption).toBeVisible();
    await expect.element(firstOption).toHaveAttribute("aria-selected", "true");

    const secondOption = component.getByRole("option", { name: relationships[1]?.display_label });
    await expect.element(secondOption).toBeVisible();
    await expect.element(secondOption).toHaveAttribute("aria-selected", "false");
  });

  it("calls onSelect when a relationship is selected", async () => {
    // GIVEN
    const relationships: Array<RelationshipNode> = [
      {
        id: "test-id-1",
        display_label: "Test Relationship 1",
        __typename: childSchema.kind,
      },
      {
        id: "test-id-2",
        display_label: "Test Relationship 2",
        __typename: childSchema.kind,
      },
    ];
    vi.mocked(getRelationships).mockResolvedValue(relationships);
    vi.mocked(useSchema).mockReturnValue({
      schema: childSchema,
      isNode: true,
      isGeneric: false,
      isProfile: false,
    });
    const onSelect = vi.fn();
    const component = render(
      <RelationshipHierarchicalComboboxList peer={childSchema.kind} onSelect={onSelect} />
    );
    const option = component.getByRole("option", { name: relationships[1]?.display_label });

    // WHEN
    await option.click();

    // THEN
    expect(onSelect).toHaveBeenCalledOnce();
    expect(onSelect).toHaveBeenCalledWith(relationships[1]);
  });
});
