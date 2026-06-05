import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Pagination } from "@/shared/components/ui/pagination";
import usePagination from "@/shared/hooks/usePagination";

import { useGetValidatorDetails } from "@/entities/diff/ui/queries/get-validator-details.query";

import { Check } from "./check";

type tValidatorDetails = {
  id: string;
};

export const ValidatorDetails = ({ id }: tValidatorDetails) => {
  const [pagination] = usePagination();

  const {
    isLoading,
    error,
    data: validator,
  } = useGetValidatorDetails({
    ids: [id],
    checksOffset: pagination?.offset,
    checksLimit: pagination?.limit,
  });

  if (isLoading) {
    return <LoadingIndicator className="p-4" />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the validator details." />;
  }

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <div className="grid min-w-0 grid-cols-1 gap-4 p-2 2xl:grid-cols-2">
        {validator?.checks?.edges?.map((check: any) => (
          <Check key={check?.node?.id} id={check?.node?.id} />
        ))}

        {!validator?.checks?.edges?.length && <NoDataFound message="No checks found." />}
      </div>
      {!!validator?.checks?.edges?.length && <Pagination count={validator?.checks?.count} />}
    </div>
  );
};
