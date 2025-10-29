import React from "react";

import {
  ObjectHierarchyTree,
  type ObjectHierarchyTreeProps,
} from "@/entities/nodes/hierarchy/ui/object-hierarchy-tree";
import { ObjectHierarchyTreeLite } from "@/entities/nodes/hierarchy/ui/object-hierarchy-tree-lite";

export function ObjectHierarchyTreeWrapper(props: ObjectHierarchyTreeProps) {
  const [initialId] = React.useState(props.currentNodeId); // Capture initial node ID on mount. The tree remains stable even when currentNodeId changes

  if (initialId) {
    return <ObjectHierarchyTreeLite {...props} initialId={initialId} />;
  }

  return <ObjectHierarchyTree {...props} />;
}
