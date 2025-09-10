import { partition } from "remeda";

import { DiffNode, DiffStatus } from "@/entities/diff/node-diff/types";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";

export type DiffTreeItem = {
  id: string;
  label: string;
  children: DiffTreeItem[];
  kind: string;
} & ({ isNode: true; hasConflicts: boolean; status: DiffStatus } | { isNode: false; icon: string });

export function buildDiffTreeItems(nodes: Array<DiffNode>): Array<DiffTreeItem> {
  if (!nodes.length) return [];

  const [nodesWithoutParent, nodesWithParent] = partition(nodes, (node) => !node.parent);

  const baseTreeItems = nodesWithoutParent.reduce<DiffTreeItem[]>((acc, node) => {
    const { kind } = node;
    const topLevelKindTreeItem = acc.find((treeItem) => treeItem.kind === kind);

    if (!topLevelKindTreeItem) {
      const newKindTreeItem = diffNodeToTreeItem(false, node);
      const newDiffTreeItem = diffNodeToTreeItem(true, node);
      newKindTreeItem.children.push(newDiffTreeItem);
      return [...acc, newKindTreeItem];
    }

    const newDiffTreeItem = diffNodeToTreeItem(true, node);
    topLevelKindTreeItem.children.push(newDiffTreeItem);
    return acc;
  }, []);

  return nodesWithParent.reduce<DiffTreeItem[]>((acc, node) => {
    const findParentTreeItem = (
      treeItems: DiffTreeItem[],
      parentId: string
    ): DiffTreeItem | undefined => {
      for (const item of treeItems) {
        if (item.id === parentId) return item;

        for (const child of item.children) {
          if (child.id === parentId) return child;

          const found = findParentTreeItem([child], parentId);
          if (found) return found;
        }
      }
    };

    const parentTreeItem = findParentTreeItem(baseTreeItems, node.parent!.uuid);
    if (!parentTreeItem) {
      return acc;
    }

    const newDiffTreeItem = diffNodeToTreeItem(true, node);
    const relationshipTreeItem = parentTreeItem.children.find(
      (rel) => rel.label === node.parent!.relationship_name
    );

    if (!relationshipTreeItem) {
      const relationshipTreeItem = diffNodeToTreeItem(false, node);
      relationshipTreeItem.id = `${node.parent!.uuid}-${node.parent!.relationship_name}`;
      relationshipTreeItem.label = node.parent!.relationship_name as string;
      relationshipTreeItem.children.push(newDiffTreeItem);
      parentTreeItem.children.push(relationshipTreeItem);
      return acc;
    }

    relationshipTreeItem.children.push(newDiffTreeItem);
    return acc;
  }, baseTreeItems);
}

function diffNodeToTreeItem(isNode: boolean, node: DiffNode): DiffTreeItem {
  if (isNode) {
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
