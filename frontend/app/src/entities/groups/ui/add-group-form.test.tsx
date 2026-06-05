import { beforeEach, describe, expect, test, vi } from "vitest";

import { queryClient } from "@/shared/api/rest/client";
import { store } from "@/shared/stores";

import { AddGroupForm } from "@/entities/groups/ui/add-group-form";
import { getRelationships } from "@/entities/nodes/relationships/domain/get-relationships/get-relationships";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../tests/components/render";
import { generateNodeSchema } from "../../../../tests/fake/schema";

vi.mock("@/entities/nodes/relationships/domain/get-relationships/get-relationships");

describe("AddGroupForm", () => {
  const groupSchema = generateNodeSchema({ kind: "CoreGroup" });
  const objectSchema = generateNodeSchema();

  const userGroup: RelationshipNode = {
    id: "group-default",
    display_label: "User Group",
    __typename: "CoreGroup",
  };
  const internalGroup: RelationshipNode = {
    id: "group-internal",
    display_label: "Internal Group",
    __typename: "CoreGroup",
  };

  beforeEach(() => {
    queryClient.clear();
    vi.clearAllMocks();
    store.set(nodeSchemasAtom, [groupSchema]);
  });

  test("hides internal groups from the manage-groups dropdown", async () => {
    // GIVEN: the API filters by group_type when the caller asks for it
    vi.mocked(getRelationships).mockImplementation(async (params) => {
      const requestedTypes = params?.filterQuery?.group_type__values as string[] | undefined;
      if (requestedTypes && !requestedTypes.includes("internal")) {
        return [userGroup];
      }
      return [userGroup, internalGroup];
    });

    const component = await render(
      <AddGroupForm objectId="object-1" schema={objectSchema} className="p-4" />
    );

    // WHEN: opening the relationship picker
    await component.getByLabelText("Add groups").click();

    // THEN
    await expect.element(component.getByRole("option", { name: "User Group" })).toBeVisible();
    await expect
      .poll(() => component.getByRole("option", { name: "Internal Group" }).query())
      .toBeNull();
  });
});
