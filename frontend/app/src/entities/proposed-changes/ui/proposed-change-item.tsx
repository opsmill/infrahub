import { ARTIFACT_OBJECT, CHECK_OBJECT, TASK_OBJECT } from "@/config/constants";
import { useObjectsCount } from "@/entities/nodes/object/domain/get-objects-count.query";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { NodeCore } from "@/entities/nodes/types";
import { ProposedChangeItem } from "@/entities/proposed-changes/domain/get-proposed-changes";
import { ProposedChangeDiffSummary } from "@/entities/proposed-changes/ui/diff-summary";
import { ProposedChangesActionCell } from "@/entities/proposed-changes/ui/proposed-changes-actions-cell";
import { getProposedChangesStateBadgeType } from "@/entities/proposed-changes/utils/proposed-changes";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { constructPath } from "@/shared/api/rest/fetch";
import { DateDisplay } from "@/shared/components/display/date-display";
import { Badge } from "@/shared/components/ui/badge";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { Icon } from "@iconify-icon/react";
import { Link } from "react-router";

type ProposedChangesItemProps = {
  node: ProposedChangeItem;
};

export const ProposedChangesItem = ({ node }: ProposedChangesItemProps) => {
  const { permission } = useObjectTableContext();

  return (
    <div className="p-2 border border-b-0 border-gray-200 flex items-center">
      <div className="flex-grow grid grid-cols-2 items-center">
        <ProposedChangesInfo
          id={node.id}
          name={node.name.value}
          author={node.created_by.node?.display_label}
          state={node.state?.value}
          isDraft={!!node.is_draft?.value}
          createdAt={node._updated_at}
          branchName={node.source_branch?.value}
        />

        <ProposedChangesData
          id={node.id}
          branchName={node.source_branch?.value}
          approvers={node.approved_by.edges.map((edge: { node: NodeCore }) => {
            return edge.node;
          })}
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
  createdAt: string;
  branchName?: string;
};

const ProposedChangesInfo = ({
  id,
  name,
  author,
  state,
  isDraft,
  createdAt,
  branchName,
}: ProposedChangesInfoProps) => {
  return (
    <div>
      <div className="flex flex-col gap-2">
        <span className="flex items-center space-x-4">
          <Link
            to={constructPath(`/proposed-changes/${id}`)}
            className="hover:text-gray-500 transition-all text-lg font-semibold"
          >
            <Icon icon={"mdi:file-replace-outline"} className="text-base" /> {name}
          </Link>

          <div className="space-x-2">
            <Badge variant={getProposedChangesStateBadgeType(state)}>{state}</Badge>
            {isDraft && <Badge variant={"gray-outline"}>draft</Badge>}
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
  approvers: Array<NodeCore>;
  comments: number;
  validations: number;
};

const ProposedChangesData = ({
  id,
  branchName,
  approvers,
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
          <ProposedChangesArtifacts id={id} />
          <ProposedChangesComments comments={comments} />
        </div>
        <ProposedChangesApprovers approvers={approvers} />
      </div>
    </div>
  );
};

const ProposedChangesApprovers = ({ approvers }: { approvers: Array<NodeCore> }) => {
  return (
    <div className="flex flex-col gap-2 text-xs">
      {!!approvers.length && (
        <div className="flex items-center gap-2">
          Approved by:{" "}
          {approvers.map((approver) => {
            return <span key={approver.id}>{approver.display_label}</span>;
          })}
        </div>
      )}
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

const ProposedChangesArtifacts = ({ id }: { id: string }) => {
  const { schema } = useSchema(ARTIFACT_OBJECT);
  const { data } = useObjectsCount({
    objectKind: ARTIFACT_OBJECT,
    filters: [{ name: "object__ids", value: [id] }],
  });

  return (
    <Tooltip enabled content="Artifacts">
      <span className="flex items-center gap-1">
        <Icon icon={schema?.icon ?? "mdi:file-outline"} /> {data ?? 0}
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
