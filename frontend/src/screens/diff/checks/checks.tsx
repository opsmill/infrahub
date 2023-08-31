import { gql } from "@apollo/client";
import { useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "../../../config/qsp";
import { getValidators } from "../../../graphql/queries/diff/getValidators";
import useQuery from "../../../hooks/useQuery";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";
import { Validator } from "./validator";
import { ValidatorDetails } from "./validator-details";

export const Checks = () => {
  const { proposedchange } = useParams();

  const [qspTab] = useQueryParam(QSP.VALIDATOR_DETAILS, StringParam);

  const queryString = getValidators({
    id: proposedchange,
  });

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data } = useQuery(query);

  const validators = data?.CoreValidator?.edges;

  if (loading) {
    return <LoadingScreen />;
  }

  if (error) {
    return <ErrorScreen />;
  }

  if (qspTab) {
    return <ValidatorDetails />;
  }

  return (
    <div>
      {validators.map((item: any, index: number) => (
        <Validator key={index} validator={item.node} />
      ))}
    </div>
  );
};
