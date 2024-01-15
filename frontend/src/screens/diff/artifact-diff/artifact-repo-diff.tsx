import { gql } from "@apollo/client";
import { useAtom } from "jotai";
import "react-diff-view/style/index.css";
import Accordion from "../../../components/display/accordion";
import { Badge } from "../../../components/display/badge";
import { getArtifactDetails } from "../../../graphql/queries/getArtifacts";
import useQuery from "../../../hooks/useQuery";
import { schemaState } from "../../../state/atoms/schema.atom";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";
import { ArtifactContentDiff } from "./artifact-content-diff";

export const ArtifactRepoDiff = (props: any) => {
  const { diff } = props;

  const [schemaList] = useAtom(schemaState);

  const schemaData = schemaList.filter((s) => s.kind === "Artifact")[0];

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
    return <LoadingScreen />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when artifact differences." />;
  }

  const artifact = data?.CoreArtifact?.edges[0]?.node?.object?.node?.display_label;

  const title = (
    <div className="flex">
      {artifact && <Badge className="mr-2">{artifact?.object?.node?.display_label}</Badge>}

      {diff.display_label}
    </div>
  );

  return (
    <div className={"rounded-lg shadow p-2 m-4 bg-custom-white"}>
      <Accordion title={title}>
        <ArtifactContentDiff itemNew={diff.item_new} itemPrevious={diff.item_previous} />
      </Accordion>
    </div>
  );
};
