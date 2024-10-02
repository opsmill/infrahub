import { ACCESS_TOKEN_KEY, ACCOUNT_GENERIC_OBJECT } from "@/config/constants";
import ObjectItemDetails from "@/screens/object-item-details/object-item-details-paginated";
import { parseJwt } from "@/utils/common";
import { useAtomValue } from "jotai";
import { genericsState } from "@/state/atoms/schema.atom";
import { useObjectDetails } from "@/hooks/useObjectDetails";
import NoDataFound from "@/screens/errors/no-data-found";
import { NetworkStatus } from "@apollo/client";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import ErrorScreen from "@/screens/errors/error-screen";
import { Card } from "@/components/ui/card";
import Content from "../layout/content";

export default function TabProfile() {
  const nodes = useAtomValue(genericsState);
  const schema = nodes.find(({ kind }) => kind === ACCOUNT_GENERIC_OBJECT);

  const localToken = localStorage.getItem(ACCESS_TOKEN_KEY);
  const tokenData = parseJwt(localToken);
  const accountId = tokenData?.sub;

  const { data, error, networkStatus } = useObjectDetails(schema, accountId);

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
    <Content className="p-2">
      <Card>
        <ObjectItemDetails schema={schema} objectDetailsData={objectDetailsData} hideHeaders />
      </Card>
    </Content>
  );
}
