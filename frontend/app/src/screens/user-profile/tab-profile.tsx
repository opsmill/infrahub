import { Card } from "@/components/ui/card";
import { ACCOUNT_GENERIC_OBJECT } from "@/config/constants";
import { ACCESS_TOKEN_KEY } from "@/config/localStorage";
import { useObjectDetails } from "@/hooks/useObjectDetails";
import ErrorScreen from "@/screens/errors/error-screen";
import NoDataFound from "@/screens/errors/no-data-found";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import ObjectItemDetails from "@/screens/object-item-details/object-item-details-paginated";
import { genericsState } from "@/state/atoms/schema.atom";
import { parseJwt } from "@/utils/common";
import { NetworkStatus } from "@apollo/client";
import { useAtomValue } from "jotai";
import Content from "../layout/content";

export default function TabProfile() {
  const nodes = useAtomValue(genericsState);
  const schema = nodes.find(({ kind }) => kind === ACCOUNT_GENERIC_OBJECT);

  const localToken = localStorage.getItem(ACCESS_TOKEN_KEY);
  const tokenData = parseJwt(localToken);
  const accountId = tokenData?.sub;

  const { data, error, networkStatus, permission } = useObjectDetails(schema, accountId);

  const objectDetailsData = schema && data && data[schema.kind!]?.edges[0]?.node;

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching user details." />;
  }

  if (networkStatus === NetworkStatus.loading) {
    return <LoadingScreen />;
  }

  if (!objectDetailsData) {
    return (
      <div className="flex column justify-center">
        <NoDataFound message="No user found for that id." />
      </div>
    );
  }

  return (
    <ObjectItemDetails
      schema={schema}
      objectDetailsData={objectDetailsData}
      permission={permission}
      hideHeaders
    />
  );
}
