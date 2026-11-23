import { beforeEach, describe, expect, test, vi } from "vitest";

import { queryClient } from "@/shared/api/rest/client";
import { store } from "@/shared/stores";

import type { RelationshipNode } from "@/entities/nodes/relationships/domain/model/relationships";
import { addRelationships } from "@/entities/nodes/relationships/domain/use-cases/add-relationships";
import { getRelationships } from "@/entities/nodes/relationships/domain/use-cases/get-relationships";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../../../tests/components/render";
import {
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../../tests/fake/schema";
import { SelectPeerForm } from "./select-peer-form";

vi.mock("@/entities/nodes/relationships/domain/use-cases/get-relationships");
vi.mock("@/entities/nodes/relationships/domain/use-cases/add-relationships");

describe("SelectPeerForm", () => {
  const tagSchema = generateNodeSchema({
    kind: "TestTag",
    name: "Tag",
    label: "Tag",
    relationships: [],
  });

  const tagsRelationshipSchema = generateRelationshipSchema({
    name: "tags",
    label: "Tags",
    peer: "TestTag",
    kind: "Attribute",
    cardinality: "many",
  });

  const tags: RelationshipNode[] = [
    { id: "tag-blue", display_label: "blue", __typename: "TestTag" },
    { id: "tag-red", display_label: "red", __typename: "TestTag" },
  ];

  beforeEach(() => {
    queryClient.clear();
    vi.mocked(addRelationships).mockReset();
    store.set(nodeSchemasAtom, [tagSchema]);
    store.set(genericSchemasAtom, []);
    vi.mocked(getRelationships).mockImplementation(async ({ peer }) =>
      peer === "TestTag" ? tags : []
    );
  });

  test("adds the selected peer to the viewed object", async () => {
    // GIVEN
    const onSuccess = vi.fn();
    const component = await render(
      <SelectPeerForm
        objectId="device-1"
        relationshipSchema={tagsRelationshipSchema}
        onSuccess={onSuccess}
        onCancel={() => {}}
      />
    );
    await component.getByRole("combobox", { name: "Tags" }).click();
    await component.getByRole("option", { name: "red" }).click();

    // WHEN
    await component.getByRole("button", { name: "Save" }).click();

    // THEN
    await expect.poll(() => onSuccess).toHaveBeenCalledOnce();
    expect(addRelationships).toHaveBeenCalledOnce();
    expect(vi.mocked(addRelationships).mock.calls[0]?.[0]).toMatchObject({
      objectId: "device-1",
      relationshipName: "tags",
      relationshipIds: ["tag-red"],
    });
  });
});
