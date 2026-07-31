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

  // Pair each node with its tree item upfront so a parent item can be found in O(1)
  // even when it appears after its children in the input
  const nodeEntries = nodes.map((node) => ({
    node,
    treeItem: createNodeTreeItemFromDiffNode(node),
  }));
  const nodeTreeItemsByUuid = new Map(
    nodeEntries.map(({ node, treeItem }) => [node.uuid, treeItem])
  );

  const [entriesWithoutParent, entriesWithParent] = partition(
    nodeEntries,
    ({ node }) => !node.parent
  );

  const baseTreeItems = entriesWithoutParent.reduce<DiffTreeItem[]>((acc, { node, treeItem }) => {
    const { kind } = node;
    const topLevelKindTreeItem = acc.find((item) => item.kind === kind);

    if (!topLevelKindTreeItem) {
      const newKindTreeItem = createGroupTreeItemFromDiffNode(node);
      newKindTreeItem.children.push(treeItem);
      return [...acc, newKindTreeItem];
    }

    topLevelKindTreeItem.children.push(treeItem);
    return acc;
  }, []);

  for (const { node, treeItem } of entriesWithParent) {
    // Nodes whose parent is not part of the diff payload are skipped, along with
    // their own children: their subtree is never linked to the returned tree
    const parentTreeItem = nodeTreeItemsByUuid.get(node.parent!.uuid);
    if (!parentTreeItem) continue;

    const relationshipName = node.parent!.relationship_name as string;
    const relationshipTreeItem = parentTreeItem.children.find(
      (rel) => !rel.isNode && rel.label === relationshipName
    );

    if (!relationshipTreeItem) {
      // Create new relationship group if it doesn't exist
      const newRelationshipTreeItem = createGroupTreeItemFromDiffNode(node);
      newRelationshipTreeItem.id = `${node.parent!.uuid}-${relationshipName}`;
      newRelationshipTreeItem.label = relationshipName;
      newRelationshipTreeItem.children.push(treeItem);
      parentTreeItem.children.push(newRelationshipTreeItem);
      continue;
    }

    // Add to existing relationship group
    relationshipTreeItem.children.push(treeItem);
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
