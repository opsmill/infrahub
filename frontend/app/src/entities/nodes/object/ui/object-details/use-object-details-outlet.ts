import { useOutletContext } from "react-router";

import type { NodeObjectWithMetadata } from "@/entities/nodes/types";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

export interface ObjectDetailsOutletContext {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
}

export const useObjectDetailsOutlet = () => useOutletContext<ObjectDetailsOutletContext>();
