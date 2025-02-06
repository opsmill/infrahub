import { useInfiniteQuery } from "@tanstack/react-query";
import { getActivitiesInfiniteQueryOptions } from "../api/get-activities.query";

export const Activities = () => {
  const { isPending, data, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteQuery(
    getActivitiesInfiniteQueryOptions()
  );
  console.log("isPending: ", isPending);
  console.log("data: ", data);

  return <div>OK</div>;
};
