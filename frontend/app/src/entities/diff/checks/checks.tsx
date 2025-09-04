import { forwardRef, useImperativeHandle } from "react";
import { useParams } from "react-router";

import useQuery from "@/shared/api/graphql/useQuery";
import ErrorScreen from "@/shared/components/errors/error-screen";

import { GET_VALIDATORS } from "@/entities/diff/api/getValidators";

import { ChecksSummary } from "./checks-summary";
import { Validator } from "./validator";

export const Checks = forwardRef((_, ref) => {
  const { proposedChangeId } = useParams();

  const { loading, error, data, refetch } = useQuery(GET_VALIDATORS, {
    notifyOnNetworkStatusChange: true,
    variables: {
      ids: [proposedChangeId],
    },
  });

  // Provide refetch function to parent
  useImperativeHandle(ref, () => ({ refetch }));

  const validators = data?.CoreValidator?.edges?.map((edge: any) => edge.node) ?? [];

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the checks list." />;
  }

  return (
    <div className="text-sm bg-stone-100 grow">
      <ChecksSummary isLoading={loading} validators={validators} refetch={refetch} />

      <div className="p-4 pt-0 space-y-2">
        {validators.map((item: any) => (
          <Validator key={item.id} validator={item} />
        ))}
      </div>
    </div>
  );
});
