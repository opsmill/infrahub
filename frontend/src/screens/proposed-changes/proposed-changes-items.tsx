import { gql } from "@apollo/client";
import { PlusIcon } from "@heroicons/react/24/outline";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { useAtomValue } from "jotai/index";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Retry } from "../../components/buttons/retry";
import { RoundedButton } from "../../components/buttons/rounded-button";
import SlideOver from "../../components/display/slide-over";
import {
  ACCOUNT_OBJECT,
  DEFAULT_BRANCH_NAME,
  PROPOSED_CHANGES_OBJECT,
} from "../../config/constants";
import { useAuth } from "../../hooks/useAuth";
import { getProposedChanges } from "../../graphql/queries/proposed-changes/getProposedChanges";
import useQuery from "../../hooks/useQuery";
import { useTitle } from "../../hooks/useTitle";
import { branchesState, currentBranchAtom } from "../../state/atoms/branches.atom";
import { schemaState } from "../../state/atoms/schema.atom";
import { constructPath } from "../../utils/fetch";
import { getObjectRelationships } from "../../utils/getSchemaObjectColumns";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import ObjectItemCreate from "../object-item-create/object-item-create-paginated";
import { getFormStructure } from "./conversations";
import { ProposedChange } from "./proposed-changes-item";

export const ProposedChanges = () => {
  const [schemaList] = useAtom(schemaState);
  const [branches] = useAtom(branchesState);
  const auth = useAuth();
  const branch = useAtomValue(currentBranchAtom);
  const navigate = useNavigate();
  const [showCreateDrawer, setShowCreateDrawer] = useState(false);

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

  const rows = edges?.map((edge: any) => edge.node);

  const customObject = {
    created_by: {
      id: auth?.data?.sub,
    },
  };

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the proposed changes list." />;
  }

  const branchesOptions: any[] = branches
    .filter((branch) => branch.name !== "main")
    .map((branch) => ({ id: branch.name, name: branch.name }));

  const reviewersOptions: any[] =
    data && accountSchemaData?.kind
      ? data[accountSchemaData.kind]?.edges.map((edge: any) => ({
          id: edge?.node.id,
          name: edge?.node?.display_label,
        }))
      : [];

  const formStructure = getFormStructure(branchesOptions, reviewersOptions);

  return (
    <div>
      <div className="bg-white flex items-center justify-between p-4 w-full">
        <div className="flex items-center">
          <h1 className="text-base font-semibold">Proposed changes ({count})</h1>

          <div className="mx-2">
            <Retry isLoading={loading} onClick={handleRefetch} />
          </div>
        </div>

        <RoundedButton
          disabled={!auth?.permissions?.write}
          onClick={() => setShowCreateDrawer(true)}
          data-cy="add-proposed-changes-button"
          data-testid="add-proposed-changes-button">
          <PlusIcon className="w-4 h-4" aria-hidden="true" />
        </RoundedButton>
      </div>

      <ul className="grid gap-6 grid-cols-1 p-6">
        {!rows && loading && <LoadingScreen />}

        {rows.map((row: any, index: number) => (
          <ProposedChange key={index} row={row} refetch={refetch} />
        ))}
      </ul>

      <SlideOver
        title={
          <div className="space-y-2">
            <div className="flex items-center w-full">
              <span className="text-lg font-semibold mr-3">Create Proposed Changes</span>
              <div className="flex-1"></div>
              <div className="flex items-center">
                <Icon icon={"mdi:layers-triple"} />
                <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
              </div>
            </div>
            <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20 mr-2">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              {schemaData?.kind}
            </span>
          </div>
        }
        open={showCreateDrawer}
        setOpen={setShowCreateDrawer}
        // title={`Create ${objectname}`}
      >
        <ObjectItemCreate
          onCreate={(response: any) => {
            setShowCreateDrawer(false);
            if (response?.object?.id) {
              const url = constructPath(`/proposed-changes/${response?.object?.id}`);
              navigate(url);
            }
          }}
          onCancel={() => setShowCreateDrawer(false)}
          objectname={PROPOSED_CHANGES_OBJECT!}
          refetch={refetch}
          formStructure={formStructure}
          customObject={customObject}
        />
      </SlideOver>
    </div>
  );
};
