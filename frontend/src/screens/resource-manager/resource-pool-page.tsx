import { useAtomValue } from "jotai";
import { useParams } from "react-router-dom";
import Content from "../layout/content";
import { ObjectHelpButton } from "../../components/menu/object-help-button";
import { iNodeSchema, schemaState } from "../../state/atoms/schema.atom";
import { useQuery } from "@apollo/client";
import { GET_KIND_FOR_RESOURCE_POOL } from "./graphql/resource-pool";
import LoadingScreen from "../loading-screen/loading-screen";
import { RESOURCE_GENERIC_KIND } from "./constants";
import NoDataFound from "../errors/no-data-found";

const ResourcePoolPage = () => {
  const { resourcePoolId } = useParams();
  const nodes = useAtomValue(schemaState);

  const { data, loading } = useQuery(GET_KIND_FOR_RESOURCE_POOL, {
    variables: { ids: [resourcePoolId] },
  });

  if (loading) return <LoadingScreen />;

  const resourcePoolData = data[RESOURCE_GENERIC_KIND].edges[0];
  if (!resourcePoolData) return <NoDataFound />;

  const { id, __typename: kind } = resourcePoolData.node;
  const schema = nodes.find((node) => node.kind === kind);
  if (!schema) return <NoDataFound />;

  return <ResourcePoolContent id={id} schema={schema} />;
};

type ResourcePoolContentProps = {
  id: string;
  schema: iNodeSchema;
};

const ResourcePoolContent = ({ id, schema }: ResourcePoolContentProps) => {
  return (
    <Content>
      <Content.Title title="Resource pool">
        {id}
        <ObjectHelpButton
          className="ml-auto"
          documentationUrl={schema.documentation}
          kind={schema.kind}
        />
      </Content.Title>
    </Content>
  );
};

export default ResourcePoolPage;
