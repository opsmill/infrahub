import { NODE_OBJECT } from "@/config/constants";
import { Skeleton } from "@/shared/components/skeleton";
import { classNames } from "@/shared/utils/common";
import { useNodeLabel } from "../api/get-display-label.query";

type NodeLabelProps = {
  id?: string;
  kind?: string;
  className?: string;
};

export const NodeLabel = ({ id, kind = NODE_OBJECT, className }: NodeLabelProps) => {
  const { isLoading, error, data } = useNodeLabel({ objectid: id, kind, enabled: !!id });

  if (isLoading) {
    return <Skeleton className="h-3 w-14" />;
  }

  if (!id) {
    return <div className="italic">No id provided</div>;
  }

  if (error || !data?.display_label) {
    return <div className={classNames("italic", className)}>{id}</div>;
  }

  return <div className={className}>{data?.display_label}</div>;
};
