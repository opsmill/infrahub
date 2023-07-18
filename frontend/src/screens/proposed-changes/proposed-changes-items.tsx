import { gql, useQuery } from "@apollo/client";
import { ChevronLeftIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useNavigate } from "react-router-dom";
import { AVATAR_SIZE, Avatar } from "../../components/avatar";
import { Badge } from "../../components/badge";
import { DateDisplay } from "../../components/date-display";
import { Tooltip } from "../../components/tooltip";
import { PROPOSED_CHANGES_OBJECT } from "../../config/constants";
import { getProposedChanges } from "../../graphql/queries/proposed-changes/getProposedChanges";
import { schemaState } from "../../state/atoms/schema.atom";
import { constructPath } from "../../utils/fetch";
import { getSchemaRelationshipColumns } from "../../utils/getSchemaObjectColumns";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";

const ProposedChange = (props: any) => {
  const { row } = props;

  const navigate = useNavigate();

  const reviewers = row.reviewers.edges.map((edge: any) => edge.node);
  const approvers = row.approved_by.edges.map((edge: any) => edge.node);

  return (
    <li
      className="col-span-1 rounded-lg bg-custom-white shadow cursor-pointer hover:bg-gray-50"
      onClick={() => navigate(constructPath(`/proposed-changes/${row.name}`))}>
      <div className="flex w-full items-center justify-between space-x-6 p-6">
        <div className="flex flex-1">
          <div className="flex flex-1 flex-col">
            <div className="flex flex-1 items-center space-x-3 mb-4">
              <div className="text-base font-semibold leading-6 text-gray-900">
                {row.name.value}
              </div>

              <div className="flex items-center">
                <Tooltip message={"Destination branch"}>
                  <Badge>{row.destination_branch.value}</Badge>
                </Tooltip>

                <ChevronLeftIcon
                  className="h-5 w-5 mx-2 flex-shrink-0 text-gray-400 mr-4"
                  aria-hidden="true"
                />

                <Tooltip message={"Source branch"}>
                  <Badge>{row.source_branch.value}</Badge>
                </Tooltip>
              </div>
            </div>

            <div className="flex flex-1 items-center space-x-3 mb-4">
              <div className="mr-2 min-w-[120px]">Reviewers:</div>

              {reviewers.map((reviewer: any, index: number) => (
                <Tooltip key={index} message={reviewer.display_label}>
                  <Avatar size={AVATAR_SIZE.SMALL} name={reviewer.display_label} />
                </Tooltip>
              ))}
            </div>

            <div className="flex flex-1 items-center space-x-3 mb-4">
              <div className="mr-2 min-w-[120px]">Approved by:</div>

              {approvers.map((approver: any, index: number) => (
                <Tooltip key={index} message={approver.display_label}>
                  <Avatar size={AVATAR_SIZE.SMALL} name={approver.display_label} />
                </Tooltip>
              ))}
            </div>
          </div>

          <div className="flex flex-col items-end">
            <div>
              Updated at: <DateDisplay date={row._updated_at} />
            </div>
          </div>
        </div>
      </div>
    </li>
  );
};

export const ProposedChanges = () => {
  const [schemaList] = useAtom(schemaState);

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

  const { loading, error, data = {} } = useQuery(query, { skip: !schemaData });

  const result = data ? data[schemaData?.kind] ?? {} : {};

  const { count, edges } = result;

  const rows = edges?.map((edge: any) => edge.node);

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
      </div>

      <ul className="grid gap-6 grid-cols-1 p-6">
        {rows.map((row: any, index: number) => (
          <ProposedChange key={index} row={row} />
        ))}
      </ul>
    </div>
  );
};
