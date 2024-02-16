import { gql } from "@apollo/client";
import { forwardRef, useImperativeHandle } from "react";
import { useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "../../../config/qsp";
import { getValidators } from "../../../graphql/queries/diff/getValidators";
import useQuery from "../../../hooks/useQuery";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";
import { ChecksSummary } from "./checks-summary";
import { Validator } from "./validator";
import { ValidatorDetails } from "./validator-details";

export const Checks = forwardRef((props, ref) => {
  const { proposedchange } = useParams();
  const [qspTab] = useQueryParam(QSP.VALIDATOR_DETAILS, StringParam);

  const queryString = getValidators({
    id: proposedchange,
  });

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data, refetch } = useQuery(query, { pollInterval: 10000 });

  // Provide refetch function to parent
  useImperativeHandle(ref, () => ({ refetch }));

  const validators = data?.CoreValidator?.edges?.map((edge: any) => edge.node);

  if (loading) {
    return <LoadingScreen />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the checks list." />;
  }

  if (qspTab) {
    return <ValidatorDetails />;
  }

  return (
    <div>
      <div className="">
        <ChecksSummary validators={validators} refetch={refetch} />
      </div>

      <div className="grid grid-cols-2 3xl:grid-cols-3 gap-4 p-4">
        {validators.map((item: any, index: number) => (
          <Validator key={index} validator={item} />
        ))}
      </div>
    </div>
  );
});
