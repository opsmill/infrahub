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

  const baseTreeItems = nodesWithoutParent.reduce<DiffTreeItem[]>((acc, node) => {
    const { kind } = node;
    const topLevelKindTreeItem = acc.find((treeItem) => treeItem.kind === kind);

    const newDiffTreeItem = createNodeTreeItemFromDiffNode(node);

    if (!topLevelKindTreeItem) {
      const newKindTreeItem = createGroupTreeItemFromDiffNode(node);
      newKindTreeItem.children.push(newDiffTreeItem);
      return [...acc, newKindTreeItem];
    }

    topLevelKindTreeItem.children.push(newDiffTreeItem);
    return acc;
  }, []);

  return nodesWithParent.reduce<DiffTreeItem[]>((acc, node) => {
    const parentTreeItem = findTreeItemById(baseTreeItems, node.parent!.uuid);
    if (!parentTreeItem) return acc;

    const newDiffTreeItem = createNodeTreeItemFromDiffNode(node);
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
      return acc;
    }

    // Add to existing relationship group
    relationshipTreeItem.children.push(newDiffTreeItem);
    return acc;
  }, baseTreeItems);
}

function findTreeItemById(treeItems: DiffTreeItem[], id: string): DiffTreeItem | undefined {
  for (const item of treeItems) {
    if (item.id === id) return item;

    for (const child of item.children) {
      if (child.id === id) return child;

      const found = findTreeItemById([child], id);
      if (found) return found;
    }
  }
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
