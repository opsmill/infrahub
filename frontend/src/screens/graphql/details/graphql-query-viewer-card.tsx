import { Link } from "react-router-dom";
import { Icon } from "@iconify-icon/react";
import { CopyToClipboard } from "../../../components/buttons/copy-to-clipboard";
import { constructPath } from "../../../utils/fetch";
import { Button } from "../../../components/buttons/button-primitive";
import { CardWithBorder } from "../../../components/ui/card";
import { GraphqlViewer } from "../../../components/editor/graphql/graphql-viewer";

const GraphqlQueryViewerCard = ({ query }: { query: string }) => {
  return (
    <CardWithBorder className="flex-grow relative">
      <GraphqlViewer value={query} />
      <div className="flex gap-2 absolute top-6 right-6">
        <CopyToClipboard variant="outline" text={query} />

        <Link to={constructPath("/graphql", [{ name: "query", value: query }])}>
          <Button variant="outline" size="sm">
            GraphQL sandbox <Icon icon="mdi:arrow-top-right" className="ml-1" />
          </Button>
        </Link>
      </div>
    </CardWithBorder>
  );
};

export default GraphqlQueryViewerCard;