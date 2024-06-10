import { Skeleton } from "../@/components/skeleton";

const GraphQLQueryDetailsPageSkeleton = () => {
  return (
    <div>
      <div className="flex bg-white h-16 justify-between items-center gap-2 px-4">
        <Skeleton className="h-8 w-full max-w-sm" />
        <Skeleton className="rounded-full h-7 w-7" />
      </div>

      <section className="flex flex-wrap lg:flex-nowrap items-start gap-4 p-4">
        <Skeleton className="w-full max-w-screen-md h-screen" />
        <Skeleton className="flex-grow h-[400px]" />
      </section>
    </div>
  );
};

export default GraphQLQueryDetailsPageSkeleton;
