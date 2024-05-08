import { Skeleton } from "../../../components/skeleton";
import { CardWithBorder } from "../../../components/ui/card";

export const IpamSummarySkeleton = () => {
  return (
    <div className="flex items-start gap-2">
      <CardWithBorder className="max-w-[479px] w-full">
        <Skeleton className="h-7 m-4" />
        <Skeleton className="h-7 m-4" />
        <Skeleton className="h-7 m-4" />
        <Skeleton className="h-7 m-4" />
        <Skeleton className="h-7 m-4" />
        <Skeleton className="h-7 m-4" />
        <Skeleton className="h-7 m-4" />
        <Skeleton className="h-7 m-4" />
        <Skeleton className="h-7 m-4" />
        <Skeleton className="h-7 m-4" />
        <Skeleton className="h-7 m-4" />
        <Skeleton className="h-7 m-4" />
      </CardWithBorder>
    </div>
  );
};
