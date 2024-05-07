import { gql } from "@apollo/client";
import { Pagination } from "../../../components/utils/pagination";
import { getValidatorDetails } from "../../../graphql/queries/diff/getValidatorDetails";
import usePagination from "../../../hooks/usePagination";
import useQuery from "../../../hooks/useQuery";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";
import NoDataFound from "../../no-data-found/no-data-found";
import { Check } from "./check";

type tValidatorDetails = {
  id: string;
};

export const ValidatorDetails = ({ id }: tValidatorDetails) => {
  const [pagination] = usePagination();

  const filtersString = [
    // Add pagination filters
    ...[
      { name: "offset", value: pagination?.offset },
      { name: "limit", value: pagination?.limit },
    ].map((row: any) => `${row.name}: ${row.value}`),
  ].join(",");

  const queryString = getValidatorDetails({
    id,
    filters: filtersString,
  });

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data } = useQuery(query);

  if (loading) {
    return <LoadingScreen hideText />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the validator details." />;
  }

  const validator = data?.CoreValidator?.edges[0]?.node;

  return (
    <div className="flex-1 flex flex-col">
      <div className="grid grid-cols-1 2xl:grid-cols-2 gap-4 p-2">
        {validator?.checks?.edges?.map((check: any) => (
          <Check key={check?.node?.id} id={check?.node?.id} />
        ))}

        {!validator?.checks?.edges?.length && <NoDataFound message="No checks found." />}
      </div>

      {!!validator?.checks?.edges?.length && <Pagination count={validator?.checks?.count} />}
    </div>
  );
};
