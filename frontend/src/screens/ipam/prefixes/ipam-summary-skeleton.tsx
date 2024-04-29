import { Skeleton } from "../../../components/skeleton";
import { CardWithBorder } from "../../../components/ui/card";

export const IpamSummarySkeleton = ({ withStats }: { withStats?: boolean }) => {
  return (
    <div className="flex items-start gap-2">
      <CardWithBorder className="max-w-[470px] w-full">
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

      {withStats && (
        <CardWithBorder className="flex-1">
          <Skeleton className="h-4 m-4" />
        </CardWithBorder>
      )}
    </div>
  );
};
