import { useParams } from "react-router";

import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { ChecksSummary } from "@/entities/diff/checks/checks-summary";
import { Validator } from "@/entities/diff/checks/validator";
import { useGetValidatorsQuery } from "@/entities/diff/domain/get-validators.query";

export const Checks = () => {
  const { proposedChangeId } = useParams();

  const {
    isPending,
    error,
    data: validators,
  } = useGetValidatorsQuery({
    proposedChangeId: proposedChangeId!,
  });

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the checks list." />;
  }

  if (isPending) {
    return <LoadingIndicator />;
  }

  if (!validators.length) {
    return <NoDataFound message="No checks for this proposed change." />;
  }

  return (
    <div className="grow bg-stone-100 text-sm">
      <ChecksSummary isLoading={isPending} validators={validators} />
      <div className="space-y-2 p-4 pt-0">
        {validators.map((item) => (
          <Validator key={item.id} validator={item} />
        ))}
      </div>
    </div>
  );
};
