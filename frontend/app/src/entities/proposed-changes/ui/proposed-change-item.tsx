import { NodeLabel } from "@/entities/nodes/object/ui/node-label";
import { constructPath } from "@/shared/api/rest/fetch";
import { DateDisplay } from "@/shared/components/display/date-display";
import { Badge } from "@/shared/components/ui/badge";
import { Icon } from "@iconify-icon/react";
import { Link } from "react-router";
import { getProposedChangesStateBadgeType } from "./proposed-changes";

export const ProposedChangesItem = ({ node }) => {
  return (
    <div>
      <ProposedChangesInfo
        id={node.id}
        name={node.name?.value}
        authorId={node.created_by?.node?.id}
        state={node.state?.value}
        createdAt={node._updated_at}
        branchName={node.source_branch?.value}
      />
    </div>
  );
};

type ProposedChangesInfoProps = {
  id: string;
  name: string;
  authorId: string;
  state: string;
  createdAt: string;
  branchName?: string;
};

const ProposedChangesInfo = ({
  id,
  name,
  authorId,
  state,
  createdAt,
  branchName,
}: ProposedChangesInfoProps) => {
  return (
    <div className="p-2 border border-b-0 border-gray-200">
      <div className="flex flex-col gap-2">
        <span className="space-x-2">
          <Badge variant={getProposedChangesStateBadgeType(state)}>{state}</Badge>
          <Link
            to={constructPath(`/proposed-changes/${id}`)}
            className="hover:text-gray-500 transition-all"
          >
            {name}
          </Link>
        </span>
        <span className="flex gap-1 text-sm">
          <Badge className="flex items-center gap-1">
            <Icon icon={"mdi:source-branch"} />
            {branchName}
          </Badge>
          Opened <DateDisplay className="text-sm font-semibold" date={createdAt} /> by{" "}
          <NodeLabel id={authorId} />
        </span>
      </div>
    </div>
  );
};
