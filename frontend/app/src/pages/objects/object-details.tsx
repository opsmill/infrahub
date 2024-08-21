import { useParams } from "react-router-dom";
import Content from "@/screens/layout/content";
import { useAtomValue } from "jotai";
import { genericsState, profilesAtom, schemaState } from "@/state/atoms/schema.atom";
import ObjectItems from "@/screens/object-items/object-items-paginated";
import ErrorScreen from "@/screens/errors/error-screen";
import { useObjectDetails } from "@/hooks/useObjectDetails";
import NoDataFound from "@/screens/errors/no-data-found";
import ObjectItemDetails from "@/screens/object-item-details/object-item-details-paginated";
import { NetworkStatus } from "@apollo/client";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { TASK_OBJECT } from "@/config/constants";
import { Card } from "@/components/ui/card";

export function ObjectDetailsPage() {
  const { objectKind, objectid } = useParams();

  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);
  const profiles = useAtomValue(profilesAtom);

  const schema = [...nodes, ...generics, ...profiles].find(({ kind }) => kind === objectKind);

  if (!schema) return <ErrorScreen message={`Object ${objectKind} not found.`} />;

  if (!objectid) return <ObjectItems schema={schema} />;

  const { data, networkStatus, error } = useObjectDetails(schema, objectid);

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the object details." />;
  }

  if (networkStatus === NetworkStatus.loading) {
    return <LoadingScreen />;
  }

  const objectDetailsData = schema && data && data[schema.kind!]?.edges[0]?.node;

  if (!objectDetailsData) {
    return (
      <div className="flex column justify-center">
        <NoDataFound message="No item found for that id." />
      </div>
    );
  }

  return (
    <Content>
      <Card className="p-2 pt-0">
        <ObjectItemDetails
          schema={schema}
          objectDetailsData={objectDetailsData}
          taskData={data[TASK_OBJECT]}
        />
      </Card>
    </Content>
  );
}

export const Component = ObjectDetailsPage;
