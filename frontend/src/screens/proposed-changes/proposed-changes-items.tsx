import { gql, useReactiveVar } from "@apollo/client";
import { PlusIcon, Square3Stack3DIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useContext, useState } from "react";
import { RoundedButton } from "../../components/rounded-button";
import SlideOver from "../../components/slide-over";
import { DEFAULT_BRANCH_NAME, PROPOSED_CHANGES_OBJECT } from "../../config/constants";
import { AuthContext } from "../../decorators/withAuth";
import { getProposedChanges } from "../../graphql/queries/proposed-changes/getProposedChanges";
import { branchVar } from "../../graphql/variables/branchVar";
import useQuery from "../../hooks/useQuery";
import { schemaState } from "../../state/atoms/schema.atom";
import { getSchemaRelationshipColumns } from "../../utils/getSchemaObjectColumns";
import { DynamicFieldData } from "../edit-form-hook/dynamic-control-types";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import ObjectItemCreate from "../object-item-create/object-item-create-paginated";
import { ProposedChange } from "./proposed-changes-item";

const formStructure: DynamicFieldData[] = [
  {
    name: "name.value",
    kind: "Text",
    type: "text",
    label: "Name",
    value: null,
    options: { values: [] },
    config: {},
    isProtected: false,
  },
  {
    name: "source_branch.value",
    kind: "Text",
    type: "text",
    label: "Source Branch",
    value: null,
    options: { values: [] },
    config: {},
    isProtected: false,
  },
  {
    name: "destination_branch.value",
    kind: "Text",
    type: "text",
    label: "Destination Branch",
    value: "main",
    options: { values: [] },
    config: {},
    isProtected: true,
  },
  {
    name: "reviewers.list",
    kind: "String",
    type: "multiselect",
    label: "Reviewers",
    value: "",
    options: {
      values: [
        { name: "Architecture Team", id: "6733eec4-ef1c-44c6-8890-1fbca82ad1a3" },
        { name: "Crm Synchronization", id: "0ad207e3-da8d-47f4-a6f7-a78a973cd1af" },
        { name: "Chloe O'Brian", id: "a0323b9c-51e1-4f82-8204-dd91f6180eea" },
        { name: "David Palmer", id: "733daf28-d8e9-4c18-bc2f-3a2305d66447" },
        { name: "Engineering Team", id: "64cb6739-1271-4279-af2d-59c0f80bdee4" },
        { name: "Jack Bauer", id: "50dfa630-8978-46ae-8475-3063d82e3cca" },
        { name: "Operation Team", id: "5686a49a-316e-473b-8204-5dbd2ebf29d2" },
        { name: "Admin", id: "da0b16fe-6c00-43a2-9b3b-379a36d6f3cc" },
        { name: "Pop-Builder", id: "adbe076b-8491-45a5-a74f-6db30078ffb2" },
      ],
    },
    config: {},
    isProtected: false,
  },
];

export const ProposedChanges = () => {
  const [schemaList] = useAtom(schemaState);

  const auth = useContext(AuthContext);

  const branch = useReactiveVar(branchVar);

  const [showCreateDrawer, setShowCreateDrawer] = useState(false);

  const schemaData = schemaList.filter((s) => s.name === PROPOSED_CHANGES_OBJECT)[0];

  const queryString = schemaData
    ? getProposedChanges({
        kind: schemaData.kind,
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

  const result = data ? data[schemaData?.kind] ?? {} : {};

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
    return <ErrorScreen />;
  }

  return (
    <div>
      <div className="bg-white sm:flex sm:items-center py-4 px-4 sm:px-6 lg:px-8 w-full">
        {schemaData && (
          <div className="sm:flex-auto flex items-center">
            <h1 className="text-xl font-semibold text-gray-900">
              {schemaData.name} ({count})
            </h1>
            <p className="mt-2 text-sm text-gray-700 m-0 pl-2 mb-1">
              A list of all the {schemaData.kind} in your infrastructure.
            </p>
          </div>
        )}

        <RoundedButton
          disabled={!auth?.permissions?.write}
          onClick={() => setShowCreateDrawer(true)}>
          <PlusIcon className="h-5 w-5" aria-hidden="true" />
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
              <span className="text-lg font-semibold mr-3">Create {PROPOSED_CHANGES_OBJECT}</span>
              <div className="flex-1"></div>
              <div className="flex items-center">
                <Square3Stack3DIcon className="w-5 h-5" />
                <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
              </div>
            </div>
            <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20">
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
          onCreate={() => setShowCreateDrawer(false)}
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
