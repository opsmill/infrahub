import type { NodeCoreWithParent } from "@/entities/nodes/object/domain/model/node";

export type IpamTreeKey = string;

/** The user's hand toggles, remembered with the prefix that was current when they were made. */
export interface IpamTreeManualExpansion {
  currentNodeId: string | undefined;
  expanded: ReadonlySet<IpamTreeKey>;
  collapsed: ReadonlySet<IpamTreeKey>;
}

export const EMPTY_MANUAL_EXPANSION: IpamTreeManualExpansion = {
  currentNodeId: undefined,
  expanded: new Set(),
  collapsed: new Set(),
};

export function getIpamTreeItemId(parentNodeId: string | null, nodeId: string): IpamTreeKey {
  return `${parentNodeId}${nodeId}`;
}

/** Keys of every ancestor row on the path to the current prefix, excluding the prefix itself. */
export function getIpamTreeAncestorKeys(
  ancestors: ReadonlyArray<NodeCoreWithParent> | undefined,
  currentNodeId: string | undefined
): Set<IpamTreeKey> {
  return new Set(
    (ancestors ?? [])
      .filter((ancestor) => ancestor.id !== currentNodeId)
      .map((ancestor) => getIpamTreeItemId(ancestor.parent?.node?.id ?? null, ancestor.id))
  );
}

/**
 * Rows to show expanded: the current prefix's ancestor path plus what the user opened by hand,
 * minus what the user closed by hand while looking at this same prefix.
 */
export function deriveIpamTreeExpandedKeys(
  ancestorKeys: ReadonlySet<IpamTreeKey>,
  manual: IpamTreeManualExpansion,
  currentNodeId: string | undefined
): Set<IpamTreeKey> {
  const keys = new Set<IpamTreeKey>([...ancestorKeys, ...manual.expanded]);
  // A collapse is only honoured for the prefix it was made on, so navigating reopens the path.
  if (manual.currentNodeId === currentNodeId) {
    for (const key of manual.collapsed) {
      keys.delete(key);
    }
  }
  return keys;
}

/** Records which rows the user just opened or closed, given the set before and after the toggle. */
export function applyIpamTreeExpansionChange(
  manual: IpamTreeManualExpansion,
  previousKeys: ReadonlySet<IpamTreeKey>,
  nextKeys: ReadonlySet<IpamTreeKey>,
  currentNodeId: string | undefined
): IpamTreeManualExpansion {
  const expanded = new Set(manual.expanded);
  const collapsed = new Set(manual.currentNodeId === currentNodeId ? manual.collapsed : []);

  for (const key of nextKeys) {
    if (!previousKeys.has(key)) {
      expanded.add(key);
      collapsed.delete(key);
    }
  }
  for (const key of previousKeys) {
    if (!nextKeys.has(key)) {
      expanded.delete(key);
      collapsed.add(key);
    }
  }

  return { currentNodeId, expanded, collapsed };
}
