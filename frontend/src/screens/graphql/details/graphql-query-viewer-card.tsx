import { Button } from "@/components/buttons/button-primitive";
import { CopyToClipboard } from "@/components/buttons/copy-to-clipboard";
import { GraphqlViewer } from "@/components/editor/graphql/graphql-viewer";
import { CardWithBorder } from "@/components/ui/card";
import { constructPath } from "@/utils/fetch";
import { Icon } from "@iconify-icon/react";
import { Link } from "react-router-dom";

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
