import { gql, useReactiveVar } from "@apollo/client";
import { ChevronRightIcon, PencilIcon, Square3Stack3DIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useContext, useState } from "react";
import Loading from "react-loading";
import { useNavigate, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { AVATAR_SIZE, Avatar } from "../../components/avatar";
import { Badge } from "../../components/badge";
import { Button } from "../../components/button";
import { DateDisplay } from "../../components/date-display";
import SlideOver from "../../components/slide-over";
import { Tabs } from "../../components/tabs";
import { Tooltip } from "../../components/tooltip";
import { DEFAULT_BRANCH_NAME, PROPOSED_CHANGES_OBJECT } from "../../config/constants";
import { QSP } from "../../config/qsp";
import { AuthContext } from "../../decorators/withAuth";
import { getProposedChanges } from "../../graphql/queries/proposed-changes/getProposedChanges";
import { branchVar } from "../../graphql/variables/branchVar";
import useQuery from "../../hooks/useQuery";
import { schemaState } from "../../state/atoms/schema.atom";
import { constructPath } from "../../utils/fetch";
import { getSchemaRelationshipColumns } from "../../utils/getSchemaObjectColumns";
import ErrorScreen from "../error-screen/error-screen";
import ObjectItemEditComponent from "../object-item-edit/object-item-edit-paginated";
import { Conversations } from "./conversations";

export const PROPOSED_CHANGES_TABS = {
  CONVERSATIONS: "conversations",
};

const tabs = [
  {
    label: "Conversations",
    name: PROPOSED_CHANGES_TABS.CONVERSATIONS,
  },
];

const renderContent = (tab: string | null | undefined) => {
  switch (tab) {
    default: {
      return <Conversations />;
    }
  }
};

export const ProposedChangesDetails = () => {
  const { proposedchange } = useParams();

  const auth = useContext(AuthContext);

  const branch = useReactiveVar(branchVar);

  const [schemaList] = useAtom(schemaState);

  const schemaData = schemaList.filter((s) => s.name === PROPOSED_CHANGES_OBJECT)[0];

  const [qspTab] = useQueryParam(QSP.PROPOSED_CHANGES_TAB, StringParam);

  const [showEditDrawer, setShowEditDrawer] = useState(false);

  const navigate = useNavigate();

  const queryString = schemaData
    ? getProposedChanges({
        id: proposedchange,
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

  const { loading, error, data, refetch } = useQuery(query, { skip: !schemaData });

  const result = data ? data[schemaData?.kind]?.edges[0]?.node : {};

  const path = constructPath("/proposed-changes");

  if (!schemaData || loading) {
    return <Loading />;
  }

  if (error) {
    return <ErrorScreen />;
  }

  const reviewers = result.reviewers.edges.map((edge: any) => edge.node);

  const approvers = result.approved_by.edges.map((edge: any) => edge.node);

  return (
    <div>
      <div className="bg-custom-white">
        <div className="py-4 px-4 w-full">
          <div className="flex items-center">
            <div className="flex flex-1">
              <div
                onClick={() => navigate(path)}
                className="text-base font-semibold leading-6 text-gray-900 cursor-pointer hover:underline">
                Proposed changes
              </div>
              <ChevronRightIcon
                className="h-5 w-5 mt-1 mx-2 flex-shrink-0 text-gray-400"
                aria-hidden="true"
              />

              <p className="mt-1 max-w-2xl text-sm text-gray-500">{proposedchange}</p>
            </div>

            <div className="">
              <Button
                disabled={!auth?.permissions?.write}
                onClick={() => setShowEditDrawer(true)}
                className="mr-4">
                Edit
                <PencilIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
          </div>
        </div>

        <div className="border-t border-b border-gray-200 px-2 py-2 sm:p-0">
          <dl className="divide-y divide-gray-200">
            <div className="py-2 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6">
              <dt className="text-sm font-medium text-gray-500">Name</dt>
              <dd className="flex mt-1 text-gray-900 sm:col-span-2 sm:mt-0">{result.name.value}</dd>
            </div>

            <div className="py-2 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6">
              <dt className="text-sm font-medium text-gray-500">Source branch</dt>
              <dd className="flex mt-1 text-gray-900 sm:col-span-2 sm:mt-0">
                <Badge>{result.source_branch.value}</Badge>
              </dd>
            </div>

            <div className="py-2 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6">
              <dt className="text-sm font-medium text-gray-500">Destination branch</dt>
              <dd className="flex mt-1 text-gray-900 sm:col-span-2 sm:mt-0">
                <Badge>{result.destination_branch.value}</Badge>
              </dd>
            </div>

            <div className="py-2 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6">
              <dt className="text-sm font-medium text-gray-500">Reviewers</dt>
              <dd className="flex mt-1 text-gray-900 sm:col-span-2 sm:mt-0">
                {reviewers.map((reviewer: any, index: number) => (
                  <Tooltip key={index} message={reviewer.display_label}>
                    <Avatar
                      size={AVATAR_SIZE.SMALL}
                      name={reviewer.display_label}
                      className="mr-2"
                    />
                  </Tooltip>
                ))}
              </dd>
            </div>

            <div className="py-2 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6">
              <dt className="text-sm font-medium text-gray-500">Approved by</dt>
              <dd className="flex mt-1 text-gray-900 sm:col-span-2 sm:mt-0">
                {approvers.map((approver: any, index: number) => (
                  <Tooltip key={index} message={approver.display_label}>
                    <Avatar
                      size={AVATAR_SIZE.SMALL}
                      name={approver.display_label}
                      className="mr-2"
                    />
                  </Tooltip>
                ))}
              </dd>
            </div>

            <div className="py-2 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6">
              <dt className="text-sm font-medium text-gray-500">Updated</dt>
              <dd className="flex mt-1 text-gray-900 sm:col-span-2 sm:mt-0">
                <DateDisplay date={result._updated_at} />
              </dd>
            </div>
          </dl>
        </div>
      </div>

      <Tabs tabs={tabs} qsp={QSP.PROPOSED_CHANGES_TAB} />

      {renderContent(qspTab)}

      <SlideOver
        title={
          <div className="space-y-2">
            <div className="flex items-center w-full">
              <span className="text-lg font-semibold mr-3">{result.display_label}</span>
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
              {schemaData.kind}
            </span>
            <div className="inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-custom-blue-500 ring-1 ring-inset ring-custom-blue-500/10 ml-3">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-custom-blue-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              ID: {result.id}
            </div>
          </div>
        }
        open={showEditDrawer}
        setOpen={setShowEditDrawer}>
        <ObjectItemEditComponent
          closeDrawer={() => setShowEditDrawer(false)}
          onUpdateComplete={() => refetch()}
          objectid={proposedchange!}
          objectname={PROPOSED_CHANGES_OBJECT!}
        />
      </SlideOver>
    </div>
  );
};
