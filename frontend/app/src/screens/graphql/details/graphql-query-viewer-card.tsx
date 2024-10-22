import { Button } from "@/components/buttons/button-primitive";
import { CopyToClipboard } from "@/components/buttons/copy-to-clipboard";
import { GraphqlViewer } from "@/components/editor/graphql/graphql-viewer";
import { Card, CardWithBorder } from "@/components/ui/card";
import { constructPath } from "@/utils/fetch";
import { Icon } from "@iconify-icon/react";
import { Link } from "react-router-dom";

const GraphqlQueryViewerCard = ({ query }: { query: string }) => {
  return (
    <Card className="flex-grow">
      <CardWithBorder.Title className="flex gap-2 items-center rounded-t">
        <h3 className="mr-auto">Query</h3>

        <CopyToClipboard variant="outline" text={query} />

        <Link to={constructPath("/graphql", [{ name: "query", value: query }])}>
          <Button variant="outline" size="sm">
            GraphQL sandbox <Icon icon="mdi:arrow-top-right" className="ml-1" />
          </Button>
        </Link>
      </CardWithBorder.Title>

      <GraphqlViewer value={query} />
    </Card>
  );
};

export default GraphqlQueryViewerCard;
