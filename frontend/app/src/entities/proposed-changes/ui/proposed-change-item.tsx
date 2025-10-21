import { Icon } from "@iconify-icon/react";
import { Link } from "react-router";

import { CHECK_OBJECT, TASK_OBJECT } from "@/config/constants";

import { constructPath } from "@/shared/api/rest/fetch";
import { DateDisplay } from "@/shared/components/display/date-display";
import { Badge } from "@/shared/components/ui/badge";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";

import { useObjectsCount } from "@/entities/nodes/object/domain/get-objects-count.query";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import type { ProposedChangeItem } from "@/entities/proposed-changes/domain/get-proposed-changes";
import { ProposedChangeDiffSummary } from "@/entities/proposed-changes/ui/diff-summary/proposed-change-diff-summary";
import { ProposedChangesActionCell } from "@/entities/proposed-changes/ui/proposed-changes-actions-cell";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

type ProposedChangesItemProps = {
  node: ProposedChangeItem;
};

export const ProposedChangesItem = ({ node }: ProposedChangesItemProps) => {
  const { permission } = useObjectTableContext();

  return (
    <div className="flex items-center border border-gray-200 border-b-0 p-2">
      <div className="grid flex-grow grid-cols-2 items-center">
        <ProposedChangesInfo
          id={node.id}
          name={node.name.value}
          author={node.created_by.node?.display_label}
          state={node.state?.value}
          isDraft={!!node.is_draft?.value}
          isApproved={!!node.approved_by.edges.length}
          createdAt={node._updated_at}
          branchName={node.source_branch?.value}
        />

        <ProposedChangesData
          id={node.id}
          branchName={node.source_branch?.value}
          comments={node.total_comments.value ?? 0}
          validations={node.validations.count}
        />
      </div>

      <ProposedChangesActionCell
        objectId={node.id}
        objectLabel={node.display_label}
        permission={permission}
      />
    </div>
  );
};

type ProposedChangesInfoProps = {
  id: string;
  name: string;
  author: string;
  state: string;
  isDraft: boolean;
  isApproved: boolean;
  createdAt: string;
  branchName?: string;
};

const ProposedChangesInfo = ({
  id,
  name,
  author,
  isDraft,
  isApproved,
  createdAt,
  branchName,
}: ProposedChangesInfoProps) => {
  return (
    <div>
      <div className="flex flex-col gap-2">
        <span className="flex items-center space-x-4">
          <Link
            to={constructPath(`/proposed-changes/${id}`)}
            className={classNames("font-semibold text-lg transition-all hover:text-gray-500")}
          >
            <Icon
              icon={"mdi:file-replace-outline"}
              className={classNames(
                "text-base",
                "text-green-700",
                isDraft && "text-gray-500",
                isApproved && "text-custom-blue-500"
              )}
            />{" "}
            {name}
          </Link>

          <div className="space-x-2">
            {isDraft && <Badge variant={"gray-outline"}>draft</Badge>}
            {isApproved && <Badge variant={"blue-outline"}>approved</Badge>}
          </div>
        </span>
        <span className="flex items-center gap-1 text-xs">
          <span className="flex items-center gap-1 font-semibold">
            <Icon icon={"mdi:source-branch"} />
            {branchName}
          </span>
          Opened <DateDisplay date={createdAt} /> by {author}
        </span>
      </div>
    </div>
  );
};

type ProposedChangesDataProps = {
  id: string;
  branchName: string;
  comments: number;
  validations: number;
};

const ProposedChangesData = ({
  id,
  branchName,
  comments,
  validations,
}: ProposedChangesDataProps) => {
  return (
    <div className="grid grid-cols-2 items-center gap-4 pr-2">
      <ProposedChangeDiffSummary proposedChangeId={id} branchName={branchName} />
      <div className="flex flex-col items-end">
        <div className="flex items-center justify-end gap-4">
          <ProposedChangesChecks validations={validations} />
          <ProposedChangesTasks id={id} />
          <ProposedChangesComments comments={comments} />
        </div>
      </div>
    </div>
  );
};

const ProposedChangesComments = ({ comments }: { comments: number }) => {
  return (
    <Tooltip enabled content="Comments">
      <span className="flex items-center gap-1">
        <Icon icon={"mdi:comment-outline"} /> {comments}
      </span>
    </Tooltip>
  );
};

const ProposedChangesChecks = ({ validations }: { validations: number }) => {
  const { schema } = useSchema(CHECK_OBJECT);

  return (
    <Tooltip enabled content="Checks">
      <span className="flex items-center">
        <Icon icon={schema?.icon ?? "mdi:check-circle-outline"} /> {validations}
      </span>
    </Tooltip>
  );
};

const ProposedChangesTasks = ({ id }: { id: string }) => {
  const { schema } = useSchema(TASK_OBJECT);
  const { data } = useObjectsCount({
    objectKind: TASK_OBJECT,
    filters: [{ name: "related_node__ids", value: [{ id }] }],
  });

  return (
    <Tooltip enabled content="Tasks">
      <span className="flex items-center gap-1">
        <Icon icon={schema?.icon ?? "mdi:subtasks"} /> {data ?? 0}
      </span>
    </Tooltip>
  );
};
