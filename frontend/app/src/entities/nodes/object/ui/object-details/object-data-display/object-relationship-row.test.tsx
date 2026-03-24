import { beforeEach, describe, expect, it, vi } from "vitest";

import { store } from "@/shared/stores";

import type {
  NodeRelationshipManyWithMetadata,
  NodeRelationshipOneWithMetadata,
} from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import type { RelationshipSchema } from "@/entities/schema/types";

import { render } from "../../../../../../../tests/components/render";
import {
  generateNodeSchema,
  generateRelationshipSchema,
} from "../../../../../../../tests/fake/schema";
import { ObjectRelationshipRow } from "./object-relationship-row";

describe("ObjectRelationshipRow", () => {
  const relatedNodeSchema = generateNodeSchema({
    kind: "TestPeer",
    name: "Peer",
    namespace: "Test",
    display_labels: ["name__value"],
  });

  const allowedPermission: Permission = {
    view: { isAllowed: true },
    create: { isAllowed: true },
    update: { isAllowed: true },
    delete: { isAllowed: true },
  };

  const deniedPermission: Permission = {
    view: { isAllowed: true },
    create: { isAllowed: true },
    update: { isAllowed: false, message: "You do not have permission to update" },
    delete: { isAllowed: true },
  };

  beforeEach(() => {
    store.set(nodeSchemasAtom, [relatedNodeSchema]);
  });

  describe("Cardinality one", () => {
    const relationshipSchemaOne: RelationshipSchema = generateRelationshipSchema({
      name: "device",
      label: "Device",
      peer: "TestPeer",
      cardinality: "one",
      read_only: false,
    });

    const relationshipDataWithNode: NodeRelationshipOneWithMetadata = {
      node: {
        id: "node-123",
        display_label: "My Device",
        __typename: "TestPeer",
      },
      properties: {
        is_protected: false,
        updated_at: "2024-01-01T00:00:00Z",
        source: null,
        owner: null,
      },
    };

    const relationshipDataWithoutNode: NodeRelationshipOneWithMetadata = {
      node: null,
      properties: {
        is_protected: false,
        updated_at: "2024-01-01T00:00:00Z",
        source: null,
        owner: null,
      },
    };

    it("renders relationship label and link to related node", async () => {
      // GIVEN
      const component = await render(
        <ObjectRelationshipRow
          relationshipSchema={relationshipSchemaOne}
          relationshipData={relationshipDataWithNode}
          permission={allowedPermission}
        />
      );

      // THEN
      await expect.element(component.getByText("Device", { exact: true })).toBeVisible();
      const link = component.getByRole("link", { name: "My Device" });
      await expect.element(link).toBeVisible();
      await expect.element(link).toHaveAttribute("href", "/objects/TestPeer/node-123");
    });

    it('renders "-" when node is null', async () => {
      // GIVEN
      const component = await render(
        <ObjectRelationshipRow
          relationshipSchema={relationshipSchemaOne}
          relationshipData={relationshipDataWithoutNode}
          permission={allowedPermission}
        />
      );

      // THEN
      await expect.element(component.getByText("Device", { exact: true })).toBeVisible();
      await expect.element(component.getByText("-")).toBeVisible();
    });

    it("shows edit-metadata pencil when onClickMetadata is provided", async () => {
      // GIVEN
      const onClickMetadata = vi.fn();
      const component = await render(
        <ObjectRelationshipRow
          relationshipSchema={relationshipSchemaOne}
          relationshipData={relationshipDataWithNode}
          permission={allowedPermission}
          onClickMetadata={onClickMetadata}
        />
      );

      // WHEN - click the metadata button to open the tooltip
      await component.getByTestId("view-metadata-button").click();

      // THEN
      const editButton = component.getByTestId("edit-metadata-button");
      await expect.element(editButton).toBeVisible();
      await expect.element(editButton).toBeEnabled();
    });

    it("disables edit-metadata pencil when permission.update.isAllowed is false", async () => {
      // GIVEN
      const onClickMetadata = vi.fn();
      const component = await render(
        <ObjectRelationshipRow
          relationshipSchema={relationshipSchemaOne}
          relationshipData={relationshipDataWithNode}
          permission={deniedPermission}
          onClickMetadata={onClickMetadata}
        />
      );

      // WHEN - click the metadata button to open the tooltip
      await component.getByTestId("view-metadata-button").click();

      // THEN
      const editButton = component.getByTestId("edit-metadata-button");
      await expect.element(editButton).toBeVisible();
      await expect.element(editButton).toBeDisabled();
    });

    it("shows lock icon when relationship is protected", async () => {
      // GIVEN
      const protectedRelationshipData: NodeRelationshipOneWithMetadata = {
        ...relationshipDataWithNode,
        properties: {
          ...relationshipDataWithNode.properties,
          is_protected: true,
        },
      };
      const component = await render(
        <ObjectRelationshipRow
          relationshipSchema={relationshipSchemaOne}
          relationshipData={protectedRelationshipData}
          permission={allowedPermission}
        />
      );

      // THEN - LockClosedIcon renders as an SVG element
      const lockIcon = component.container.querySelector("svg");
      expect(lockIcon).not.toBeNull();
    });
  });

  describe("Cardinality many", () => {
    const relationshipSchemaMany: RelationshipSchema = generateRelationshipSchema({
      name: "tags",
      label: "Tags",
      peer: "TestPeer",
      cardinality: "many",
      read_only: false,
    });

    const relationshipDataEmpty: NodeRelationshipManyWithMetadata = {
      edges: [],
    };

    const relationshipDataWithEdges: NodeRelationshipManyWithMetadata = {
      edges: [
        {
          node: {
            id: "tag-1",
            display_label: "Tag One",
            __typename: "TestPeer",
          },
          properties: {
            is_protected: false,
            updated_at: "2024-01-01T00:00:00Z",
            source: null,
            owner: null,
          },
        },
        {
          node: {
            id: "tag-2",
            display_label: "Tag Two",
            __typename: "TestPeer",
          },
          properties: {
            is_protected: true,
            updated_at: "2024-01-02T00:00:00Z",
            source: null,
            owner: null,
          },
        },
      ],
    };

    it('renders "-" when edges is empty', async () => {
      // GIVEN
      const component = await render(
        <ObjectRelationshipRow
          relationshipSchema={relationshipSchemaMany}
          relationshipData={relationshipDataEmpty}
          permission={allowedPermission}
        />
      );

      // THEN
      await expect.element(component.getByText("Tags")).toBeVisible();
      await expect.element(component.getByText("-")).toBeVisible();
    });

    it("renders multiple related node links when edges exist", async () => {
      // GIVEN
      const component = await render(
        <ObjectRelationshipRow
          relationshipSchema={relationshipSchemaMany}
          relationshipData={relationshipDataWithEdges}
          permission={allowedPermission}
        />
      );

      // THEN
      await expect.element(component.getByText("Tags")).toBeVisible();

      const linkOne = component.getByRole("link", { name: "Tag One" });
      await expect.element(linkOne).toBeVisible();
      await expect.element(linkOne).toHaveAttribute("href", "/objects/TestPeer/tag-1");

      const linkTwo = component.getByRole("link", { name: "Tag Two" });
      await expect.element(linkTwo).toBeVisible();
      await expect.element(linkTwo).toHaveAttribute("href", "/objects/TestPeer/tag-2");
    });
  });
});
