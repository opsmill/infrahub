import { afterAll, afterEach, beforeAll, describe, expect, test, vi } from "vitest";

import { store } from "@/shared/stores";

import { getDiffTreeFromApi } from "@/entities/diff/api/get-diff-tree-from-api";
import { getDiffTreeSummaryFromApi } from "@/entities/diff/api/get-diff-tree-summary-from-api";
import { NodeDiff } from "@/entities/diff/ui/node-diff";
import type { DiffNode } from "@/entities/diff/ui/node-diff/types";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../tests/components/render";
import { generateNodeSchema } from "../../../../../tests/fake/schema";

vi.mock("@/entities/diff/api/get-diff-tree-from-api");
vi.mock("@/entities/diff/api/get-diff-tree-summary-from-api");

describe("NodeDiff", () => {
  const getDiffTreeFromApiMock = vi.mocked(getDiffTreeFromApi);
  const getDiffTreeSummaryFromApiMock = vi.mocked(getDiffTreeSummaryFromApi);

  const initialNodeSchemas = store.get(nodeSchemasAtom);

  beforeAll(() => {
    store.set(nodeSchemasAtom, [
      generateNodeSchema({ kind: "TestDevice", label: "Device" }),
      generateNodeSchema({ kind: "TestInterface", label: "Interface" }),
    ]);
  });

  afterAll(() => {
    store.set(nodeSchemasAtom, initialNodeSchemas);
  });

  afterEach(() => {
    vi.clearAllMocks();
    window.history.replaceState(null, "", window.location.pathname);
  });

  test("shows a changed node in the diff tree when its parent node is unchanged", async () => {
    // GIVEN a diff where an updated interface belongs to a device without changes,
    // returned by the backend as hierarchy context with status UNCHANGED (include_parents)
    const unchangedParent: DiffNode = {
      uuid: "device-1",
      kind: "TestDevice",
      label: "atl1-edge1",
      status: "UNCHANGED",
      parent: null,
      attributes: [],
      relationships: [],
      contains_conflict: false,
      conflict: null,
      path_identifier: "",
      last_changed_at: "2026-07-22T00:00:00Z",
    };
    const updatedChild: DiffNode = {
      uuid: "interface-1",
      kind: "TestInterface",
      label: "Ethernet1",
      status: "UPDATED",
      parent: { uuid: "device-1", kind: "TestDevice", relationship_name: "interfaces" },
      attributes: [
        {
          uuid: "attribute-1",
          name: "description",
          contains_conflict: false,
          conflict: null,
          path_identifier: "",
          properties: [
            {
              property_type: "HAS_VALUE",
              new_value: "new description",
              previous_value: "old description",
              status: "UPDATED",
              conflict: null,
              path_identifier: "",
              last_changed_at: "2026-07-22T00:00:00Z",
            },
          ],
        },
      ],
      relationships: [],
      contains_conflict: false,
      conflict: null,
      path_identifier: "",
      last_changed_at: "2026-07-22T00:00:00Z",
    };

    getDiffTreeFromApiMock.mockResolvedValue({
      data: {
        DiffTree: {
          nodes: [unchangedParent, updatedChild],
          to_time: "2026-07-22T00:00:00Z",
          from_time: "2026-07-21T00:00:00Z",
          base_branch: "main",
          diff_branch: "test-branch",
        },
      },
    } as unknown as Awaited<ReturnType<typeof getDiffTreeFromApi>>);
    getDiffTreeSummaryFromApiMock.mockResolvedValue({
      data: {
        DiffTreeSummary: { num_added: 0, num_updated: 1, num_removed: 0, num_conflicts: 0 },
      },
    } as unknown as Awaited<ReturnType<typeof getDiffTreeSummaryFromApi>>);

    // WHEN
    const component = await render(<NodeDiff branch="test-branch" />);

    // THEN the updated interface is listed in the right-hand diff list
    await expect.element(component.getByRole("link", { name: "Ethernet1" })).toBeVisible();

    // THEN its unchanged parent device appears in the left tree as hierarchy context
    const parentRow = component.getByRole("row", { name: /atl1-edge1/ });
    await expect.element(parentRow).toBeVisible();

    // WHEN expanding the parent device and its relationship group
    await parentRow.getByRole("button").click();
    const relationshipRow = component.getByRole("row", { name: /interfaces/ });
    await relationshipRow.getByRole("button").click();

    // THEN the updated interface appears in the left tree, nested under its parent
    await expect.element(component.getByRole("row", { name: /Ethernet1/ })).toBeVisible();
  });

  test("shows a conflicted node in both panes when its parent is unchanged and the conflicts filter is active", async () => {
    // GIVEN the conflicts filter is active
    window.history.replaceState(null, "", "?status=CONFLICT");

    // AND a diff where a conflicted interface belongs to an unchanged device
    // (contains_conflict never propagates to ancestor nodes), next to an updated
    // device without conflicts
    const unchangedParent: DiffNode = {
      uuid: "device-1",
      kind: "TestDevice",
      label: "atl1-edge1",
      status: "UNCHANGED",
      parent: null,
      attributes: [],
      relationships: [],
      contains_conflict: false,
      conflict: null,
      path_identifier: "",
      last_changed_at: "2026-07-22T00:00:00Z",
    };
    const conflictedChild: DiffNode = {
      uuid: "interface-1",
      kind: "TestInterface",
      label: "Ethernet1",
      status: "UPDATED",
      parent: { uuid: "device-1", kind: "TestDevice", relationship_name: "interfaces" },
      attributes: [
        {
          uuid: "attribute-1",
          name: "description",
          contains_conflict: true,
          conflict: null,
          path_identifier: "",
          properties: [
            {
              property_type: "HAS_VALUE",
              new_value: "new description",
              previous_value: "old description",
              status: "UPDATED",
              conflict: null,
              path_identifier: "",
              last_changed_at: "2026-07-22T00:00:00Z",
            },
          ],
        },
      ],
      relationships: [],
      contains_conflict: true,
      conflict: null,
      path_identifier: "",
      last_changed_at: "2026-07-22T00:00:00Z",
    };
    const updatedNodeWithoutConflict: DiffNode = {
      uuid: "device-2",
      kind: "TestDevice",
      label: "atl1-edge2",
      status: "UPDATED",
      parent: null,
      attributes: [],
      relationships: [],
      contains_conflict: false,
      conflict: null,
      path_identifier: "",
      last_changed_at: "2026-07-22T00:00:00Z",
    };

    getDiffTreeFromApiMock.mockResolvedValue({
      data: {
        DiffTree: {
          nodes: [unchangedParent, conflictedChild, updatedNodeWithoutConflict],
          to_time: "2026-07-22T00:00:00Z",
          from_time: "2026-07-21T00:00:00Z",
          base_branch: "main",
          diff_branch: "test-branch",
        },
      },
    } as unknown as Awaited<ReturnType<typeof getDiffTreeFromApi>>);
    getDiffTreeSummaryFromApiMock.mockResolvedValue({
      data: {
        DiffTreeSummary: { num_added: 0, num_updated: 2, num_removed: 0, num_conflicts: 1 },
      },
    } as unknown as Awaited<ReturnType<typeof getDiffTreeSummaryFromApi>>);

    // WHEN
    const component = await render(<NodeDiff branch="test-branch" />);

    // THEN the conflicted interface is listed in the right-hand diff list,
    // while the updated device without conflicts is filtered out
    await expect.element(component.getByRole("link", { name: "Ethernet1" })).toBeVisible();
    await expect
      .element(component.getByRole("link", { name: "atl1-edge2" }))
      .not.toBeInTheDocument();

    // THEN its unchanged parent device appears in the left tree as hierarchy context
    const parentRow = component.getByRole("row", { name: /atl1-edge1/ });
    await expect.element(parentRow).toBeVisible();

    // WHEN expanding the parent device and its relationship group
    await parentRow.getByRole("button").click();
    const relationshipRow = component.getByRole("row", { name: /interfaces/ });
    await relationshipRow.getByRole("button").click();

    // THEN the conflicted interface appears in the left tree, nested under its parent
    await expect.element(component.getByRole("row", { name: /Ethernet1/ })).toBeVisible();
  });
});
