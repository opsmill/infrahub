import { gql } from "@apollo/client";
import { PlusIcon } from "@heroicons/react/24/outline";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { useContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import { RoundedButton } from "../../components/rounded-button";
import SlideOver from "../../components/slide-over";
import {
  ACCOUNT_OBJECT,
  DEFAULT_BRANCH_NAME,
  PROPOSED_CHANGES_OBJECT,
} from "../../config/constants";
import { AuthContext } from "../../decorators/withAuth";
import { getProposedChanges } from "../../graphql/queries/proposed-changes/getProposedChanges";
import useQuery from "../../hooks/useQuery";
import { branchesState, currentBranchAtom } from "../../state/atoms/branches.atom";
import { schemaState } from "../../state/atoms/schema.atom";
import { constructPath } from "../../utils/fetch";
import { getSchemaRelationshipColumns } from "../../utils/getSchemaObjectColumns";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import ObjectItemCreate from "../object-item-create/object-item-create-paginated";
import { getFormStructure } from "./conversations";
import { ProposedChange } from "./proposed-changes-item";
import { useAtomValue } from "jotai/index";

export const ProposedChanges = () => {
  const [schemaList] = useAtom(schemaState);
  const [branches] = useAtom(branchesState);
  const auth = useContext(AuthContext);
  const branch = useAtomValue(currentBranchAtom);
  const navigate = useNavigate();
  const [showCreateDrawer, setShowCreateDrawer] = useState(false);

  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_OBJECT);
  const accountSchemaData = schemaList.find((s) => s.kind === ACCOUNT_OBJECT);

  const queryString = schemaData
    ? getProposedChanges({
        kind: schemaData.kind,
        accountKind: accountSchemaData?.kind,
        attributes: schemaData.attributes,
        relationships: getSchemaRelationshipColumns(schemaData),
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schemaData
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data = {}, refetch } = useQuery(query, { skip: !schemaData });

  const result = data && schemaData?.kind ? data[schemaData?.kind] ?? {} : {};

  const { count, edges } = result;

  const rows = edges?.map((edge: any) => edge.node);

  const customObject = {
    created_by: {
      id: auth?.data?.sub,
    },
  };

  if (!schemaData || loading) {
    return <LoadingScreen />;
  }

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
      <div className="bg-white flex items-center p-4 w-full">
        {schemaData && (
          <div className="sm:flex-auto flex items-center">
            <h1 className="text-md font-semibold text-gray-900">
              {schemaData.name} ({count})
            </h1>
          </div>
        )}

        <RoundedButton
          disabled={!auth?.permissions?.write}
          onClick={() => setShowCreateDrawer(true)}
          data-cy="add-proposed-changes-button">
          <PlusIcon className="w-4 h-4" aria-hidden="true" />
        </RoundedButton>
      </div>

      <ul className="grid gap-6 grid-cols-1 p-6">
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
