import { CardWithBorder } from "../../../components/ui/card";
import { Skeleton } from "../../../components/skeleton";

export const IpamPrefixSummarySkeleton = () => {
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

      <CardWithBorder>
        <Skeleton className="h-[219px] w-[219px] rounded-full m-10" />
        <Skeleton className="h-4 w-10/12 m-4" />
      </CardWithBorder>
    </div>
  );
};
