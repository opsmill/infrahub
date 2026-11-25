import { Checkbox } from "@infrahub/ui";

import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Pagination } from "@/shared/components/ui/pagination";
import usePagination from "@/shared/hooks/usePagination";

import { useGetValidatorDetails } from "@/entities/diff/ui/queries/get-validator-details.query";

import { Check } from "./check";

type tValidatorDetails = {
  id: string;
  artifactSort?: {
    failedFirst: boolean;
    onChange: (failedFirst: boolean) => void;
  };
};

export const ValidatorDetails = ({ id, artifactSort }: tValidatorDetails) => {
  const paginationKey = artifactSort ? `artifact-checks-${id}` : undefined;
  const [pagination, setPagination] = usePagination({ urlKey: paginationKey });

  const {
    isLoading,
    error,
    data: validator,
  } = useGetValidatorDetails({
    ids: [id],
    checksOffset: pagination?.offset,
    checksLimit: pagination?.limit,
    checksFailedFirst: artifactSort?.failedFirst,
  });

  if (isLoading) {
    return <LoadingIndicator className="p-4" />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the validator details." />;
  }

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      {artifactSort && (
        <Checkbox
          className="self-end px-2 pt-2"
          isSelected={artifactSort.failedFirst}
          onChange={(failedFirst) => {
            setPagination({ ...pagination, offset: 0 });
            artifactSort.onChange(failedFirst);
          }}
        >
          Failed first
        </Checkbox>
      )}
      <div className="grid min-w-0 grid-cols-1 gap-4 p-2 2xl:grid-cols-2">
        {validator?.checks?.edges?.map(({ node }) =>
          node?.id ? <Check key={node.id} id={node.id} /> : null
        )}

        {!validator?.checks?.edges?.length && <NoDataFound message="No checks found." />}
      </div>
      {!!validator?.checks?.edges?.length && (
        <Pagination
          key={artifactSort?.failedFirst ? "failed-first" : "default"}
          count={validator?.checks?.count}
          urlKey={paginationKey}
        />
      )}
    </div>
  );
};
