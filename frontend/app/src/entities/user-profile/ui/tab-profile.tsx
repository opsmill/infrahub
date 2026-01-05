import { NetworkStatus } from "@apollo/client";
import { useAtomValue } from "jotai";

import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ACCOUNT_GENERIC_OBJECT } from "@/shared/config/constants";
import { parseJwt } from "@/shared/utils/common";

import { ACCESS_TOKEN_KEY } from "@/entities/authentication/constants";
import { useObjectDetails } from "@/entities/nodes/hooks/useObjectDetails";
import ObjectItemDetails from "@/entities/nodes/object-item-details/object-item-details-paginated";
import { genericSchemasAtom } from "@/entities/schema/stores/schema.atom";

export default function TabProfile() {
  const nodes = useAtomValue(genericSchemasAtom);
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
    return <LoadingIndicator className="h-[244px]" />;
  }

  if (!objectDetailsData) {
    return (
      <div className="column flex justify-center">
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
