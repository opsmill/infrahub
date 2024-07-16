import { Button, ButtonWithTooltip } from "@/components/buttons/button-primitive";
import { Badge } from "@/components/ui/badge";
import { ACCOUNT_OBJECT, PROPOSED_CHANGES_OBJECT } from "@/config/constants";
import { getProposedChanges } from "@/graphql/queries/proposed-changes/getProposedChanges";
import { usePermission } from "@/hooks/usePermission";
import useQuery from "@/hooks/useQuery";
import { useTitle } from "@/hooks/useTitle";
import ErrorScreen from "@/screens/errors/error-screen";
import Content from "@/screens/layout/content";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { schemaState } from "@/state/atoms/schema.atom";
import { constructPath } from "@/utils/fetch";
import { getObjectRelationships } from "@/utils/getSchemaObjectColumns";
import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { Link } from "react-router-dom";
import { ProposedChange } from "@/screens/proposed-changes/proposed-changes-item";

const ProposedChangesPage = () => {
  const [schemaList] = useAtom(schemaState);
  const permission = usePermission();
  useTitle("Proposed changes list");

  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_OBJECT);
  const accountSchemaData = schemaList.find((s) => s.kind === ACCOUNT_OBJECT);
  const relationships = getObjectRelationships({ schema: schemaData, forListView: true });

  const queryString = schemaData
    ? getProposedChanges({
        kind: schemaData.kind,
        accountKind: accountSchemaData?.kind,
        attributes: schemaData.attributes,
        relationships,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schemaData
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  const {
    loading,
    error,
    data = {},
    refetch,
  } = useQuery(query, { skip: !schemaData, notifyOnNetworkStatusChange: true });

  const handleRefetch = () => refetch();

  const result = data && schemaData?.kind ? data[schemaData?.kind] ?? {} : {};

  const { count = "...", edges = [] } = result;

  const rows = edges?.map((edge: any) => edge.node).reverse();

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the proposed changes list." />;
  }

  return (
    <Content>
      <Content.Title
        title={
          <>
            Proposed changes <Badge>{count}</Badge>
          </>
        }
        reload={handleRefetch}
        isReloadLoading={loading}>
        {permission.write.allow ? (
          <Link className="ml-auto" to={constructPath("/proposed-changes/new")}>
            <Button size="icon" variant="outline" data-testid="add-proposed-changes-button">
              <Icon icon="mdi:plus" />
            </Button>
          </Link>
        ) : (
          <ButtonWithTooltip
            className="ml-auto"
            size="icon"
            variant="outline"
            disabled
            tooltipEnabled
            tooltipContent={permission.write.message ?? undefined}
            data-testid="add-proposed-changes-button">
            <Icon icon="mdi:plus" />
          </ButtonWithTooltip>
        )}
      </Content.Title>

      <ul className="grid gap-6 grid-cols-1 p-6">
        {!rows && loading && <LoadingScreen />}

        {rows.map((row: any, index: number) => (
          <ProposedChange key={index} row={row} refetch={refetch} />
        ))}
      </ul>
    </Content>
  );
};

export function Component() {
  return <ProposedChangesPage />;
}
