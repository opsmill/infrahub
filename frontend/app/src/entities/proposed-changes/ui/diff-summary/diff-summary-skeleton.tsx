import { Row } from "@/shared/components/container";
import { Skeleton } from "@/shared/components/loading/skeleton";

export function DiffSummarySkeleton() {
  return (
    <Row>
      {[...Array(4)].map((_, index) => (
        <Skeleton key={index} className="h-6 w-9 rounded-full" />
      ))}
    </Row>
  );
}
