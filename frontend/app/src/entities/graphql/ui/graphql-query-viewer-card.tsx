import { Icon } from "@iconify-icon/react";
import { Link } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Button } from "@/shared/components/buttons/button-primitive";
import { CopyToClipboard } from "@/shared/components/buttons/copy-to-clipboard";
import { CodeViewer } from "@/shared/components/editor/code/code-viewer";
import { Card, CardWithBorder } from "@/shared/components/ui/card";

const GraphqlQueryViewerCard = ({ query }: { query: string }) => {
  return (
    <Card className="grow overflow-x-hidden p-0">
      <CardWithBorder.Title className="flex items-center gap-2 rounded-t">
        <h3 className="mr-auto">Query</h3>

        <CopyToClipboard variant="outline" text={query} />

        <Link to={constructPath("/graphql", [{ name: "query", value: query }])}>
          <Button variant="outline" size="sm">
            GraphQL sandbox <Icon icon="mdi:arrow-top-right" className="ml-1" />
          </Button>
        </Link>
      </CardWithBorder.Title>

      <CodeViewer language="graphql">{query}</CodeViewer>
    </Card>
  );
};

export default GraphqlQueryViewerCard;
