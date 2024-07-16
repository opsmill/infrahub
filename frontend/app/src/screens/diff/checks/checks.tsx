import { GET_VALIDATORS } from "@/graphql/queries/diff/getValidators";
import useQuery from "@/hooks/useQuery";
import ErrorScreen from "@/screens/errors/error-screen";
import { forwardRef, useImperativeHandle } from "react";
import { useParams } from "react-router-dom";
import { ChecksSummary } from "./checks-summary";
import { Validator } from "./validator";

export const Checks = forwardRef((props, ref) => {
  const { proposedchange } = useParams();

  const { loading, error, data, refetch } = useQuery(GET_VALIDATORS, {
    notifyOnNetworkStatusChange: true,
    variables: {
      ids: [proposedchange],
    },
  });

  // Provide refetch function to parent
  useImperativeHandle(ref, () => ({ refetch }));

  const validators = data?.CoreValidator?.edges?.map((edge: any) => edge.node) ?? [];

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the checks list." />;
  }

  return (
    <div className="text-sm">
      <ChecksSummary isLoading={loading} validators={validators} refetch={refetch} />

      <div className="p-4 pt-0 space-y-2">
        {validators.map((item: any) => (
          <Validator key={item.id} validator={item} />
        ))}
      </div>
    </div>
  );
});
