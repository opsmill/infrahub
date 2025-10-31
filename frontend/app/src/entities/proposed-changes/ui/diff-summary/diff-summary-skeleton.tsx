import { Row } from "@/shared/components/container";

export function DiffSummarySkeleton() {
  return (
    <Row>
      {[...Array(4)].map((_, index) => (
        <div key={index} className="h-6 w-9 animate-pulse rounded-full bg-gray-200" />
      ))}
    </Row>
  );
}
