import { gql } from "@apollo/client";
import { useAtom } from "jotai";

import useQuery from "@/shared/api/graphql/useQuery";
import Accordion from "@/shared/components/display/accordion";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { Badge } from "@/shared/components/ui/badge";

import { getArtifactDetails } from "@/entities/artifacts/api/getArtifacts";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import "react-diff-view/style/index.css";

import { Row } from "@/shared/components/container";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { ArtifactContentDiff } from "./artifact-content-diff";

export const ArtifactRepoDiff = (props: any) => {
  const { diff } = props;

  const [schemaList] = useAtom(nodeSchemasAtom);

  const schemaData = schemaList.find((s) => s.kind === "Artifact");

  const queryString = schemaData
    ? getArtifactDetails({
        id: diff.id,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schemaData
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data } = useQuery(query, { skip: !schemaData });

  if (loading) {
    return <LoadingIndicator className="m-4 h-10" />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when artifact differences." />;
  }

  if (!diff) {
    return <NoDataFound message="No artifact diff" />;
  }

  const artifactNode = data?.CoreArtifact?.edges[0]?.node?.object?.node;

  const title = (
    <Row>
      {artifactNode && <Badge className="font-normal">{getNodeLabel(artifactNode)}</Badge>}
      {diff?.display_label}
    </Row>
  );

  return (
    <div className={"m-4 rounded-lg bg-white p-2 shadow-sm"} id={diff.id}>
      <Accordion title={title}>
        <ArtifactContentDiff
          id={diff.id}
          itemNew={diff.item_new}
          itemPrevious={diff.item_previous}
        />
      </Accordion>
    </div>
  );
};
