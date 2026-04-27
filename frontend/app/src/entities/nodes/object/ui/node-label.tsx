import { Skeleton } from "@/shared/components/loading/skeleton";
import { NODE_OBJECT } from "@/shared/config/constants";
import { classNames } from "@/shared/utils/common";

import { useNodeLabel } from "@/entities/nodes/object/ui/queries/get-display-label.query";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeCore } from "@/entities/nodes/types";

type NodeLabelProps = {
  id?: string | null;
  kind?: string;
  branch?: string | null;
  className?: string;
  // Pre-resolved node from a parent batched query. When provided (even as
  // null), the component skips its own per-id fetch — used to avoid the
  // per-related-node fan-out described in #9067.
  resolved?: NodeCore | null;
  // When true, render a skeleton without firing an internal query.
  loading?: boolean;
};

export const NodeLabel = ({
  id,
  kind = NODE_OBJECT,
  branch,
  className,
  resolved,
  loading: externalLoading,
}: NodeLabelProps) => {
  const useExternalSource = resolved !== undefined || !!externalLoading;

  const { isPending, error, data } = useNodeLabel({
    objectId: id,
    kind,
    enabled: !!id && !useExternalSource,
    branch,
  });

  if (externalLoading) {
    return <Skeleton className="h-3 w-14" />;
  }

  if (!id) {
    return <div className="italic">No id provided</div>;
  }

  if (useExternalSource) {
    if (!resolved) {
      return <div className={classNames("italic", className)}>{id}</div>;
    }
    return <div className={classNames("contents", className)}>{getNodeLabel(resolved)}</div>;
  }

  if (isPending) {
    return <Skeleton className="h-3 w-14" />;
  }

  if (error || !data) {
    return <div className={classNames("italic", className)}>{id}</div>;
  }

  return <div className={classNames("contents", className)}>{getNodeLabel(data)}</div>;
};
