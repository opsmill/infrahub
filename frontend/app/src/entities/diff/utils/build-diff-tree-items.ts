import { partition } from "remeda";

import type { DiffNode, DiffStatus } from "@/entities/diff/ui/node-diff/types";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";

export interface BaseTreeItem {
  id: string;
  label: string;
  children: DiffTreeItem[];
  kind: string;
}

export interface NodeTreeItem extends BaseTreeItem {
  isNode: true;
  hasConflicts: boolean;
  status: DiffStatus;
}

export interface GroupTreeItem extends BaseTreeItem {
  isNode: false;
  icon: string;
}

export type DiffTreeItem = NodeTreeItem | GroupTreeItem;

export function buildDiffTreeItems(nodes: Array<DiffNode>): Array<DiffTreeItem> {
  if (!nodes.length) return [];

  const [nodesWithoutParent, nodesWithParent] = partition(nodes, (node) => !node.parent);

  // Pre-create one tree item per node so a parent can be found in O(1) even when
  // it appears after its children in the input
  const nodeTreeItemsByUuid = new Map(
    nodes.map((node) => [node.uuid, createNodeTreeItemFromDiffNode(node)])
  );

  const baseTreeItems = nodesWithoutParent.reduce<DiffTreeItem[]>((acc, node) => {
    const { kind } = node;
    const topLevelKindTreeItem = acc.find((treeItem) => treeItem.kind === kind);

    const newDiffTreeItem = nodeTreeItemsByUuid.get(node.uuid)!;

    if (!topLevelKindTreeItem) {
      const newKindTreeItem = createGroupTreeItemFromDiffNode(node);
      newKindTreeItem.children.push(newDiffTreeItem);
      return [...acc, newKindTreeItem];
    }

    topLevelKindTreeItem.children.push(newDiffTreeItem);
    return acc;
  }, []);

  for (const node of nodesWithParent) {
    // Nodes whose parent is not part of the diff payload are skipped, along with
    // their own children: their subtree is never linked to the returned tree
    const parentTreeItem = nodeTreeItemsByUuid.get(node.parent!.uuid);
    if (!parentTreeItem) continue;

    const newDiffTreeItem = nodeTreeItemsByUuid.get(node.uuid)!;
    const relationshipName = node.parent!.relationship_name as string;
    const relationshipTreeItem = parentTreeItem.children.find(
      (rel) => !rel.isNode && rel.label === relationshipName
    );

    if (!relationshipTreeItem) {
      // Create new relationship group if it doesn't exist
      const newRelationshipTreeItem = createGroupTreeItemFromDiffNode(node);
      newRelationshipTreeItem.id = `${node.parent!.uuid}-${relationshipName}`;
      newRelationshipTreeItem.label = relationshipName;
      newRelationshipTreeItem.children.push(newDiffTreeItem);
      parentTreeItem.children.push(newRelationshipTreeItem);
      continue;
    }

    // Add to existing relationship group
    relationshipTreeItem.children.push(newDiffTreeItem);
  }

  return baseTreeItems;
}

function createNodeTreeItemFromDiffNode(node: DiffNode): NodeTreeItem {
  return {
    isNode: true,
    id: node.uuid,
    kind: node.kind,
    label: node.label,
    hasConflicts: node.contains_conflict,
    status: node.status,
    children: [],
  };
}

function createGroupTreeItemFromDiffNode(node: DiffNode): GroupTreeItem {
  const { schema } = getSchema(node.kind);
  return {
    isNode: false,
    id: node.kind,
    label: schema?.label ?? node.kind,
    kind: node.kind,
    icon: getSchemaIcon(schema),
    children: [],
  };
}
