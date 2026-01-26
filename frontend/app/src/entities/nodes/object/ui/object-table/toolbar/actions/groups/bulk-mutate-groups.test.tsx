import { beforeEach, describe, expect, test, vi } from "vitest";

import { store } from "@/shared/stores";

import { getRelationships } from "@/entities/nodes/relationships/domain/get-relationships/get-relationships";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../../../../tests/components/render";
import { generateNodeSchema } from "../../../../../../../../../tests/fake/schema";
import { BulkMutateGroups } from "./bulk-mutate-groups";

vi.mock("@/entities/nodes/relationships/domain/get-relationships/get-relationships");

describe("BulkMutateGroups Component", () => {
  const mockGroups: RelationshipNode[] = [
    { id: "group-1", display_label: "Test Group 1", __typename: "CoreGroup" },
    { id: "group-2", display_label: "Test Group 2", __typename: "CoreGroup" },
  ];

  const mockMutationFn = vi.fn().mockResolvedValue(undefined);
  const mockOnSuccess = vi.fn();
  const groupSchema = generateNodeSchema({ kind: "CoreGroup" });

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getRelationships).mockResolvedValue({ items: mockGroups, count: mockGroups.length });
    store.set(nodeSchemasAtom, [groupSchema]);
  });

  test("renders the group selector", async () => {
    // GIVEN
    const component = await render(
      <BulkMutateGroups mutationFn={mockMutationFn} onSuccess={mockOnSuccess} />
    );

    // THEN
    await expect.element(component.getByTestId("group-selector")).toBeVisible();
  });

  test("adds a group to the selected groups panel when a group is selected", async () => {
    // GIVEN
    const component = await render(
      <BulkMutateGroups mutationFn={mockMutationFn} onSuccess={mockOnSuccess} />
    );

    // WHEN
    await component.getByRole("option", { name: "Test Group 1" }).click();

    // THEN
    await expect.element(component.getByTestId("selected-groups-panel")).toBeVisible();
    await expect
      .element(
        component
          .getByTestId("selected-groups-panel")
          .getByRole("option", { name: "Test Group 1 Remove from" })
      )
      .toBeVisible();
  });

  test("removes a group when clicking the remove button", async () => {
    // GIVEN
    const component = await render(
      <BulkMutateGroups mutationFn={mockMutationFn} onSuccess={mockOnSuccess} />
    );

    // WHEN
    await component.getByRole("option", { name: "Test Group 1" }).click(); // Select the first group
    await component.getByRole("button", { name: "Remove from group Test Group 1" }).click(); // Then remove it

    // THEN
    await expect.poll(() => component.getByTestId("selected-groups-panel").query()).toBeNull();
  });

  test("filters out already selected groups", async () => {
    // GIVEN
    const component = await render(
      <BulkMutateGroups mutationFn={mockMutationFn} onSuccess={mockOnSuccess} />
    );

    // WHEN
    await component.getByRole("option", { name: "Test Group 1" }).click();

    // THEN
    await expect
      .element(
        component.getByTestId("group-selector").getByRole("option", { name: "Test Group 2" })
      )
      .toBeVisible();
    await expect
      .poll(() =>
        component
          .getByTestId("group-selector")
          .getByRole("option", { name: "Test Group 1" })
          .query()
      )
      .toBeNull();
  });

  test("transitions to processing state when validate button is clicked", async () => {
    // GIVEN
    const component = await render(
      <BulkMutateGroups mutationFn={mockMutationFn} onSuccess={mockOnSuccess} />
    );

    // WHEN
    await component.getByRole("option", { name: "Test Group 1" }).click();
    await component.getByRole("button", { name: "Validate" }).click();

    // THEN
    await expect.element(component.getByTestId("processing-groups-panel")).toBeVisible();
    await expect.poll(() => component.getByTestId("group-selector").query()).toBeNull();
  });

  test("calls mutation function when processing", async () => {
    // GIVEN
    const component = await render(
      <BulkMutateGroups mutationFn={(group) => mockMutationFn(group)} onSuccess={mockOnSuccess} />
    );

    // WHEN
    await component.getByRole("option", { name: "Test Group 1" }).click();
    await component.getByRole("button", { name: "Validate" }).click();

    // THEN
    expect(mockMutationFn).toHaveBeenCalledExactlyOnceWith(mockGroups[0]);
  });

  test("handles multiple group selections", async () => {
    // GIVEN
    const component = await render(
      <BulkMutateGroups mutationFn={mockMutationFn} onSuccess={mockOnSuccess} />
    );

    // WHEN
    await component.getByRole("option", { name: "Test Group 1" }).click();
    await component.getByRole("option", { name: "Test Group 2" }).click();

    // THEN
    await expect
      .element(
        component
          .getByTestId("selected-groups-panel")
          .getByRole("option", { name: "Test Group 1 Remove from" })
      )
      .toBeVisible();
    await expect
      .element(
        component
          .getByTestId("selected-groups-panel")
          .getByRole("option", { name: "Test Group 2 Remove from" })
      )
      .toBeVisible();
  });
});
