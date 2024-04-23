import { gql } from "@apollo/client";
import { useAtom } from "jotai";
import { ACCOUNT_OBJECT, PROPOSED_CHANGES_OBJECT } from "../../config/constants";
import { getProposedChanges } from "../../graphql/queries/proposed-changes/getProposedChanges";
import useQuery from "../../hooks/useQuery";
import { useTitle } from "../../hooks/useTitle";
import { schemaState } from "../../state/atoms/schema.atom";
import { getObjectRelationships } from "../../utils/getSchemaObjectColumns";
import ErrorScreen from "../error-screen/error-screen";
import Content from "../layout/content";
import LoadingScreen from "../loading-screen/loading-screen";
import { ProposedChange } from "./proposed-changes-item";
import { usePermission } from "../../hooks/usePermission";
import { Link } from "react-router-dom";
import { RoundedButton } from "../../components/buttons/rounded-button";
import { PlusIcon } from "@heroicons/react/24/outline";
import { Tooltip } from "../../components/ui/tooltip";
import { Badge } from "../../components/ui/badge";
import { constructPath } from "../../utils/fetch";

const ProposedChanges = () => {
  const [schemaList] = useAtom(schemaState);
  const permission = usePermission();
  useTitle("Proposed changes list");

  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_OBJECT);
  const accountSchemaData = schemaList.find((s) => s.kind === ACCOUNT_OBJECT);
  const relationships = getObjectRelationships(schemaData, true);

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
        <div className="flex-grow text-right">
          {permission.write.allow ? (
            <Link to={constructPath("/proposed-changes/new")}>
              <RoundedButton
                disabled={!permission.write.allow}
                data-testid="add-proposed-changes-button">
                <PlusIcon className="w-4 h-4" aria-hidden="true" />
              </RoundedButton>
            </Link>
          ) : (
            <Tooltip content={permission.write.message ?? undefined}>
              <RoundedButton
                disabled={!permission.write.allow}
                data-testid="add-proposed-changes-button">
                <PlusIcon className="w-4 h-4" aria-hidden="true" />
              </RoundedButton>
            </Tooltip>
          )}
        </div>
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

export default ProposedChanges;
