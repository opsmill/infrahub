import { gql } from "@apollo/client";
import { forwardRef, useImperativeHandle } from "react";
import { useParams } from "react-router-dom";
import { getValidators } from "../../../graphql/queries/diff/getValidators";
import useQuery from "../../../hooks/useQuery";
import ErrorScreen from "../../error-screen/error-screen";
import { ChecksSummary } from "./checks-summary";
import { Validator } from "./validator";

export const Checks = forwardRef((props, ref) => {
  const { proposedchange } = useParams();

  const queryString = getValidators({
    id: proposedchange,
  });

  const query = gql`
    ${queryString}
  `;

  const { error, data, refetch } = useQuery(query, { notifyOnNetworkStatusChange: true });

  // Provide refetch function to parent
  useImperativeHandle(ref, () => ({ refetch }));

  const validators = data?.CoreValidator?.edges?.map((edge: any) => edge.node) ?? [];

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the checks list." />;
  }

  return (
    <div>
      <div>
        <ChecksSummary validators={validators} refetch={refetch} />
      </div>

      <div className="p-4">
        {validators.map((item: any, index: number) => (
          <Validator key={index} validator={item} />
        ))}
      </div>
    </div>
  );
});
