import { gql, useReactiveVar } from "@apollo/client";
import { ChevronLeftIcon, TrashIcon } from "@heroicons/react/24/outline";
import { useContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../components/alert";
import { AVATAR_SIZE, Avatar } from "../../components/avatar";
import { Badge } from "../../components/badge";
import { BUTTON_TYPES, Button } from "../../components/button";
import { DateDisplay } from "../../components/date-display";
import ModalDelete from "../../components/modal-delete";
import { Tooltip } from "../../components/tooltip";
import { PROPOSED_CHANGES_OBJECT } from "../../config/constants";
import { AuthContext } from "../../decorators/withAuth";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { deleteObject } from "../../graphql/mutations/objects/deleteObject";
import { branchVar } from "../../graphql/variables/branchVar";
import { dateVar } from "../../graphql/variables/dateVar";
import { constructPath } from "../../utils/fetch";
import { getProposedChangesStateBadgeType } from "../../utils/proposed-changes";
import { stringifyWithoutQuotes } from "../../utils/string";

export const ProposedChange = (props: any) => {
  const { row, refetch } = props;

  const branch = useReactiveVar(branchVar);
  const date = useReactiveVar(dateVar);
  const auth = useContext(AuthContext);
  const [isLoading, setIsLoading] = useState(false);
  const [deleteModal, setDeleteModal] = useState(false);

  const navigate = useNavigate();

  const reviewers = row.reviewers.edges.map((edge: any) => edge.node);

  const approvers = row.approved_by.edges.map((edge: any) => edge.node);

  const handleDeleteObject = async () => {
    if (!row.id) {
      return;
    }

    setIsLoading(true);

    const mutationString = deleteObject({
      kind: PROPOSED_CHANGES_OBJECT,
      data: stringifyWithoutQuotes({
        id: row.id,
      }),
    });

    const mutation = gql`
      ${mutationString}
    `;

    await graphqlClient.mutate({
      mutation,
      context: { branch: branch?.name, date },
    });

    refetch();

    setDeleteModal(false);

    setIsLoading(false);

    toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Proposed changes deleted"} />);
  };

  return (
    <li
      className="relative col-span-1 rounded-lg bg-custom-white shadow cursor-pointer hover:bg-gray-50 group/pc"
      onClick={() => navigate(constructPath(`/proposed-changes/${row.id}`))}>
      <Button
        buttonType={BUTTON_TYPES.INVISIBLE}
        className="absolute -right-4 -top-4 hidden group-hover/pc:block"
        onClick={() => setDeleteModal(true)}
        disabled={!auth?.permissions?.write}>
        <TrashIcon className="h-4 w-4 text-red-500" />
      </Button>

      <div className="flex w-full items-center justify-between space-x-6 p-6">
        <div className="flex flex-1">
          <div className="flex flex-1 flex-col">
            <div className="flex flex-1 items-center space-x-3 mb-4">
              <div>
                <Badge type={getProposedChangesStateBadgeType(row?.state?.value)}>
                  {row?.state?.value}
                </Badge>
              </div>

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

              <div className="flex items-center space-x-3">
                <div>Created by:</div>

                <Tooltip message={row?.created_by?.node?.display_label}>
                  <Avatar
                    size={AVATAR_SIZE.SMALL}
                    name={row?.created_by?.node?.display_label}
                    className="bg-custom-blue-green"
                  />
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
            <div className="flex items-center">
              <div className="mr-2">Updated:</div>
              <DateDisplay date={row._updated_at} />
            </div>
          </div>
        </div>
      </div>

      <ModalDelete
        title="Delete"
        description={"Are you sure you want to remove this proposed changes?"}
        onCancel={() => setDeleteModal(false)}
        onDelete={handleDeleteObject}
        open={!!deleteModal}
        setOpen={() => setDeleteModal(false)}
        isLoading={isLoading}
      />
    </li>
  );
};
