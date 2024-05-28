import { Skeleton } from "../../../components/skeleton";

const GraphQLQueryDetailsPageSkeleton = () => {
  return (
    <section className="flex flex-wrap lg:flex-nowrap items-start gap-4 p-4">
      <Skeleton className="w-full max-w-screen-md h-screen" />
      <Skeleton className="flex-grow h-[400px]" />
    </section>
  );
};

export default GraphQLQueryDetailsPageSkeleton;
