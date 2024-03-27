import { gql } from "@apollo/client";
import { PlusIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { Link } from "react-router-dom";
import { Retry } from "../../components/buttons/retry";
import { RoundedButton } from "../../components/buttons/rounded-button";
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
import { constructPath } from "../../utils/fetch";
import { Tooltip } from "../../components/ui/tooltip";
import { usePermission } from "../../hooks/usePermission";

export const ProposedChanges = () => {
  const [schemaList] = useAtom(schemaState);
  const permission = usePermission();

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

  useTitle("Proposed changes list");

  const rows = edges?.map((edge: any) => edge.node).reverse();

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the proposed changes list." />;
  }

  return (
    <Content>
      <div className="bg-white flex items-center justify-between p-4 w-full">
        <div className="flex items-center">
          <h1 className="text-base font-semibold">Proposed changes ({count})</h1>

          <div className="mx-2">
            <Retry isLoading={loading} onClick={handleRefetch} />
          </div>
        </div>

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

      <ul className="grid gap-6 grid-cols-1 p-6">
        {!rows && loading && <LoadingScreen />}

        {rows.map((row: any, index: number) => (
          <ProposedChange key={index} row={row} refetch={refetch} />
        ))}
      </ul>
    </Content>
  );
};
