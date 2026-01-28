import { constructPath } from "@/shared/api/rest/fetch";
import { DataViewer } from "@/shared/components/data-viewer/data-viewer";
import { DataViewerLinkButton } from "@/shared/components/data-viewer/data-viewer-action-button";

export function GraphqlQueryViewerCard({ query }: { query: string }) {
  return (
    <DataViewer
      title="Query"
      data={query}
      fileName="query.graphql"
      contentType="application/graphql"
      actions={
        <DataViewerLinkButton href={constructPath("/graphql", [{ name: "query", value: query }])}>
          GraphQL sandbox
        </DataViewerLinkButton>
      }
    />
  );
}
