import { NODE_OBJECT } from "@/config/constants";
import { Skeleton } from "@/shared/components/skeleton";
import { classNames } from "@/shared/utils/common";
import { useDisplayLabel } from "../api/get-display-label.query";

type DisplayLabelProps = {
  id: string;
  kind?: string;
  className?: string;
};

export const DisplayLabel = ({ id, kind = NODE_OBJECT, className }: DisplayLabelProps) => {
  const { isLoading, error, data } = useDisplayLabel({ objectid: id, kind });

  const object = data?.data?.[kind]?.edges?.[0]?.node ?? {};

  if (isLoading) {
    return <Skeleton className="h-3 w-14" />;
  }

  if (error || !object?.display_label) {
    return <div className="italic">Name not found</div>;
  }

  return <div className={classNames(className)}>{object?.display_label}</div>;
};
