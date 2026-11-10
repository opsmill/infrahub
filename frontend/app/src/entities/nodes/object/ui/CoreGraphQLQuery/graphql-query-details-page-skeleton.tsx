import { Skeleton } from "@/shared/components/loading/skeleton";

export function GraphQLQueryDetailsPageSkeleton() {
  return (
    <div>
      <div className="flex h-16 items-center justify-between gap-2 bg-content px-4">
        <Skeleton className="h-8 w-full max-w-sm" />
        <Skeleton className="h-7 w-7 rounded-full" />
      </div>

      <section className="flex flex-wrap items-start gap-4 p-4 lg:flex-nowrap">
        <Skeleton className="h-screen w-full max-w-(--breakpoint-md)" />
        <Skeleton className="h-100 grow" />
      </section>
    </div>
  );
}
