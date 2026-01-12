import { Skeleton } from "@/shared/components/loading/skeleton";
import { NODE_OBJECT } from "@/shared/config/constants";
import { classNames } from "@/shared/utils/common";

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";

import { useNodeLabel } from "../api/get-display-label.query";

type NodeLabelProps = {
  id?: string;
  kind?: string;
  branch?: string | null;
  className?: string;
};

export const NodeLabel = ({ id, kind = NODE_OBJECT, branch, className }: NodeLabelProps) => {
  const { isPending, error, data } = useNodeLabel({ objectId: id, kind, enabled: !!id, branch });

  if (isPending) {
    return <Skeleton className="h-3 w-14" />;
  }

  if (!id) {
    return <div className="italic">No id provided</div>;
  }

  if (error || !data) {
    return <div className={classNames("italic", className)}>{id}</div>;
  }

  return <div className={classNames("contents", className)}>{getNodeLabel(data)}</div>;
};
