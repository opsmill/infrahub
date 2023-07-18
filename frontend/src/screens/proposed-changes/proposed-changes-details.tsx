import { gql } from "@apollo/client";
import { ChevronRightIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import Loading from "react-loading";
import { useNavigate, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { AVATAR_SIZE, Avatar } from "../../components/avatar";
import { Badge } from "../../components/badge";
import { DateDisplay } from "../../components/date-display";
import { Tabs } from "../../components/tabs";
import { Tooltip } from "../../components/tooltip";
import { PROPOSED_CHANGES_OBJECT } from "../../config/constants";
import { QSP } from "../../config/qsp";
import { getProposedChanges } from "../../graphql/queries/proposed-changes/getProposedChanges";
import useQuery from "../../hooks/useQuery";
import { schemaState } from "../../state/atoms/schema.atom";
import { constructPath } from "../../utils/fetch";
import { getSchemaRelationshipColumns } from "../../utils/getSchemaObjectColumns";
import ErrorScreen from "../error-screen/error-screen";

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
      return null;
    }
  }
};

export const ProposedChangesDetails = () => {
  const { proposedchange } = useParams();
  console.log("proposedchange: ", proposedchange);

  const [schemaList] = useAtom(schemaState);

  const schemaData = schemaList.filter((s) => s.name === PROPOSED_CHANGES_OBJECT)[0];

  const [qspTab] = useQueryParam(QSP.PROPOSED_CHANGES_TAB, StringParam);

  const navigate = useNavigate();

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

  const { loading, error, data } = useQuery(query, { skip: !schemaData });

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
    <div className="bg-custom-white">
      <div className="py-4 px-4 w-full">
        <div className="flex items-center">
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
                  <Avatar size={AVATAR_SIZE.SMALL} name={reviewer.display_label} className="mr-2" />
                </Tooltip>
              ))}
            </dd>
          </div>

          <div className="py-2 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6">
            <dt className="text-sm font-medium text-gray-500">Approved by</dt>
            <dd className="flex mt-1 text-gray-900 sm:col-span-2 sm:mt-0">
              {approvers.map((approver: any, index: number) => (
                <Tooltip key={index} message={approver.display_label}>
                  <Avatar size={AVATAR_SIZE.SMALL} name={approver.display_label} className="mr-2" />
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

      <Tabs tabs={tabs} qsp={QSP.PROPOSED_CHANGES_TAB} />

      {renderContent(qspTab)}
    </div>
  );
};
