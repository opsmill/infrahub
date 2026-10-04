import { describe, expect, it } from "vitest";

import {
  applyIpamTreeExpansionChange,
  deriveIpamTreeExpandedKeys,
  EMPTY_MANUAL_EXPANSION,
  getIpamTreeAncestorKeys,
  getIpamTreeItemId,
} from "@/entities/ipam/ipam-tree/domain/rules/derive-ipam-tree-expanded-keys";
import type { NodeCoreWithParent } from "@/entities/nodes/object/domain/model/node";

const ROOT_ID = "root";
const SUPERNET_ID = "supernet";
const CHILD_ID = "child";

const ancestorsOfChild: NodeCoreWithParent[] = [
  { id: ROOT_ID, display_label: "0.0.0.0/0", __typename: "IpamPrefix", parent: { node: null } },
  {
    id: SUPERNET_ID,
    display_label: "10.0.0.0/8",
    __typename: "IpamPrefix",
    parent: { node: { id: ROOT_ID, display_label: "0.0.0.0/0", __typename: "IpamPrefix" } },
  },
  {
    id: CHILD_ID,
    display_label: "10.1.0.0/16",
    __typename: "IpamPrefix",
    parent: { node: { id: SUPERNET_ID, display_label: "10.0.0.0/8", __typename: "IpamPrefix" } },
  },
];

const ROOT_KEY = getIpamTreeItemId(null, ROOT_ID);
const SUPERNET_KEY = getIpamTreeItemId(ROOT_ID, SUPERNET_ID);
const CHILD_KEY = getIpamTreeItemId(SUPERNET_ID, CHILD_ID);

describe("getIpamTreeAncestorKeys", () => {
  it("returns the keys of the path above the current prefix but not the prefix itself", () => {
    // GIVEN the ancestors of a /16 two levels below the root
    // WHEN the ancestor keys are computed for that /16
    const keys = getIpamTreeAncestorKeys(ancestorsOfChild, CHILD_ID);

    // THEN the root and the supernet rows are keyed, the /16 is not
    expect([...keys]).toEqual([ROOT_KEY, SUPERNET_KEY]);
  });

  it("returns no keys when the ancestors are not loaded yet", () => {
    // GIVEN no ancestor data
    // WHEN the ancestor keys are computed
    const keys = getIpamTreeAncestorKeys(undefined, CHILD_ID);

    // THEN nothing is expanded by the path
    expect(keys.size).toBe(0);
  });
});

describe("deriveIpamTreeExpandedKeys", () => {
  it("opens the ancestor path and keeps what the user opened elsewhere", () => {
    // GIVEN the user opened an unrelated row by hand
    const manual = { ...EMPTY_MANUAL_EXPANSION, expanded: new Set(["nullother"]) };

    // WHEN the expanded set is derived for the /16
    const keys = deriveIpamTreeExpandedKeys(new Set([ROOT_KEY, SUPERNET_KEY]), manual, CHILD_ID);

    // THEN the path and the manual row are both open
    expect([...keys].sort()).toEqual([ROOT_KEY, SUPERNET_KEY, "nullother"].sort());
  });

  it("honours a collapse made while looking at the same prefix", () => {
    // GIVEN the user collapsed the supernet row while on the /16
    const manual = {
      ...EMPTY_MANUAL_EXPANSION,
      currentNodeId: CHILD_ID,
      collapsed: new Set([SUPERNET_KEY]),
    };

    // WHEN the expanded set is derived for the same /16
    const keys = deriveIpamTreeExpandedKeys(new Set([ROOT_KEY, SUPERNET_KEY]), manual, CHILD_ID);

    // THEN the supernet stays collapsed
    expect([...keys]).toEqual([ROOT_KEY]);
  });

  it("reopens a collapsed path once the user navigates to another prefix", () => {
    // GIVEN the user collapsed the supernet row while on a different prefix
    const manual = {
      ...EMPTY_MANUAL_EXPANSION,
      currentNodeId: "elsewhere",
      collapsed: new Set([SUPERNET_KEY]),
    };

    // WHEN the expanded set is derived for the /16
    const keys = deriveIpamTreeExpandedKeys(new Set([ROOT_KEY, SUPERNET_KEY]), manual, CHILD_ID);

    // THEN the whole path is open again
    expect([...keys]).toEqual([ROOT_KEY, SUPERNET_KEY]);
  });
});

describe("applyIpamTreeExpansionChange", () => {
  it("records a row the user opened", () => {
    // GIVEN only the root is open
    const previous = new Set([ROOT_KEY]);

    // WHEN the user opens the supernet
    const manual = applyIpamTreeExpansionChange(
      EMPTY_MANUAL_EXPANSION,
      previous,
      new Set([ROOT_KEY, SUPERNET_KEY]),
      CHILD_ID
    );

    // THEN the supernet is remembered as opened for this prefix
    expect([...manual.expanded]).toEqual([SUPERNET_KEY]);
    expect(manual.collapsed.size).toBe(0);
    expect(manual.currentNodeId).toBe(CHILD_ID);
  });

  it("records a row the user closed and forgets it was opened", () => {
    // GIVEN the supernet was opened by hand earlier
    const manual = {
      ...EMPTY_MANUAL_EXPANSION,
      currentNodeId: CHILD_ID,
      expanded: new Set([SUPERNET_KEY]),
    };

    // WHEN the user closes it
    const next = applyIpamTreeExpansionChange(
      manual,
      new Set([ROOT_KEY, SUPERNET_KEY]),
      new Set([ROOT_KEY]),
      CHILD_ID
    );

    // THEN it is remembered as collapsed and no longer as expanded
    expect(next.expanded.size).toBe(0);
    expect([...next.collapsed]).toEqual([SUPERNET_KEY]);
  });

  it("drops collapses made on a previous prefix when a toggle happens on a new one", () => {
    // GIVEN a collapse recorded while on another prefix
    const manual = {
      ...EMPTY_MANUAL_EXPANSION,
      currentNodeId: "elsewhere",
      collapsed: new Set([CHILD_KEY]),
    };

    // WHEN the user opens the supernet on the /16
    const next = applyIpamTreeExpansionChange(
      manual,
      new Set([ROOT_KEY]),
      new Set([ROOT_KEY, SUPERNET_KEY]),
      CHILD_ID
    );

    // THEN the old collapse is gone and the new prefix owns the toggles
    expect(next.collapsed.size).toBe(0);
    expect(next.currentNodeId).toBe(CHILD_ID);
  });
});
