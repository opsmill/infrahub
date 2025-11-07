import { Icon } from "@iconify-icon/react";
import { ListBoxItem } from "react-aria-components";
import { Link } from "react-router";

import { CHECK_OBJECT } from "@/config/constants";

import { constructPath } from "@/shared/api/rest/fetch";
import { DateDisplay } from "@/shared/components/display/date-display";
import { Badge } from "@/shared/components/ui/badge";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";

import type { ProposedChangeItem } from "@/entities/proposed-changes/domain/get-proposed-changes";
import { ProposedChangeDiffSummary } from "@/entities/proposed-changes/ui/diff-summary/proposed-change-diff-summary";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

type ProposedChangesItemLightProps = {
  node: ProposedChangeItem;
};

export const ProposedChangesItemLight = ({ node }: ProposedChangesItemLightProps) => {
  return (
    <ListBoxItem className="flex items-center p-4">
      <div className="grid flex-grow grid-cols-2 items-center">
        <ProposedChangesInfo
          id={node.id}
          name={node.name.value}
          isDraft={!!node.is_draft?.value}
          isApproved={!!node.approved_by.edges.length}
        />

        <ProposedChangesData
          id={node.id}
          branchName={node.source_branch?.value}
          comments={node.total_comments.value ?? 0}
          validations={node.validations.count}
          updatedAt={node._updated_at}
        />
      </div>
    </ListBoxItem>
  );
};

type ProposedChangesInfoProps = {
  id: string;
  name: string;
  isDraft: boolean;
  isApproved: boolean;
};

const ProposedChangesInfo = ({ id, name, isDraft, isApproved }: ProposedChangesInfoProps) => {
  return (
    <span className="flex min-w-0 max-w-full items-center gap-4 whitespace-nowrap">
      <Link
        to={constructPath(`/proposed-changes/${id}`)}
        className={classNames("truncate font-semibold transition-all hover:text-gray-500")}
      >
        {name}
      </Link>

      <div className="flex-shrink-0 space-x-2">
        {isDraft && <Badge variant={"gray-outline"}>draft</Badge>}
        {isApproved && <Badge variant={"blue-outline"}>approved</Badge>}
      </div>
    </span>
  );
};

type ProposedChangesDataProps = {
  id: string;
  branchName: string;
  comments: number;
  validations: number;
  updatedAt: string;
};

const ProposedChangesData = ({
  id,
  branchName,
  comments,
  validations,
  updatedAt,
}: ProposedChangesDataProps) => {
  return (
    <div className="grid grid-cols-7 items-center gap-4 text-gray-500">
      <ProposedChangesComments comments={comments} />

      <ProposedChangeDiffSummary
        proposedChangeId={id}
        branchName={branchName}
        className="col-span-3 flex items-center justify-center"
      />

      <ProposedChangesChecks validations={validations} />

      <DateDisplay
        date={updatedAt}
        containerClassName={"col-span-2 text-right justify-end"}
        dateFormat="d MMM yyyy hh:mm"
      />
    </div>
  );
};

const ProposedChangesComments = ({ comments }: { comments: number }) => {
  if (!comments) {
    return <div />;
  }

  return (
    <Tooltip enabled content="Comments">
      <span className="flex items-center justify-center gap-1">
        <Icon icon={"mdi:comment-outline"} /> {comments}
      </span>
    </Tooltip>
  );
};

const ProposedChangesChecks = ({ validations }: { validations: number }) => {
  const { schema } = useSchema(CHECK_OBJECT);

  return (
    <Tooltip enabled content="Checks">
      <span className="flex items-center justify-center">
        <Icon icon={schema?.icon ?? "mdi:check-circle-outline"} /> {validations}
      </span>
    </Tooltip>
  );
};
