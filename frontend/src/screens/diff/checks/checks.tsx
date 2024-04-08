import { forwardRef, useImperativeHandle } from "react";
import { useParams } from "react-router-dom";
import useQuery from "../../../hooks/useQuery";
import ErrorScreen from "../../error-screen/error-screen";
import { ChecksSummary } from "./checks-summary";
import { Validator } from "./validator";
import { GET_VALIDATORS } from "../../../graphql/queries/diff/getValidators";

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
    <div className="text-xs">
      <ChecksSummary isLoading={loading} validators={validators} refetch={refetch} />

      <div className="p-4 pt-0">
        {validators.map((item: any, index: number) => (
          <Validator key={index} validator={item} />
        ))}
      </div>
    </div>
  );
});
