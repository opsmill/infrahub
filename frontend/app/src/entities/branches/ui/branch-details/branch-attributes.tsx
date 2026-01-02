import {
  BoxIcon,
  CheckIcon,
  CircleIcon,
  GitCommitIcon,
  IdCardIcon,
  RefreshCwIcon,
  XIcon,
} from "lucide-react";

import { DateDisplay } from "@/shared/components/display/date-display";
import { Card } from "@/shared/components/ui/card";
import { classNames } from "@/shared/utils/common";

import { BRANCH_STATUS } from "@/entities/branches/constants";
import type { BranchDetail } from "@/entities/branches/domain/branch.mappers";

interface BranchAttributesProps {
  branch: BranchDetail;
}

export function BranchAttributes({ branch }: BranchAttributesProps) {
  return (
    <Card className="grid w-fit grid-cols-[auto_1fr] gap-x-6 gap-y-1.5">
      <BranchAttributeLabel>
        <IdCardIcon className="size-3.5" /> Name
      </BranchAttributeLabel>
      <BranchAttributeValue>{branch.name}</BranchAttributeValue>

      {branch.status !== BRANCH_STATUS.OPEN && (
        <>
          <BranchAttributeLabel>
            <CircleIcon className="size-3.5" /> Status
          </BranchAttributeLabel>
          <BranchAttributeValue>{branch.status}</BranchAttributeValue>
        </>
      )}

      <BranchAttributeLabel>
        <RefreshCwIcon className="size-3.5" /> Sync with Git
      </BranchAttributeLabel>
      <BranchAttributeValue>
        {branch.sync_with_git ? <CheckIcon className="size-4" /> : <XIcon className="size-4" />}
      </BranchAttributeValue>

      {!branch.is_default && (
        <>
          <BranchAttributeLabel>
            <BoxIcon className="size-3.5" /> Has schema changes
          </BranchAttributeLabel>
          <BranchAttributeValue>
            {branch.has_schema_changes ? (
              <CheckIcon className="size-4" />
            ) : (
              <XIcon className="size-4" />
            )}
          </BranchAttributeValue>

          <BranchAttributeLabel>
            <GitCommitIcon className="size-3.5" /> Last rebase
          </BranchAttributeLabel>

          <BranchAttributeValue>
            <DateDisplay date={branch.branched_from} className="text-sm" />
          </BranchAttributeValue>
        </>
      )}
    </Card>
  );
}

export function BranchAttributeLabel({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={classNames(
        "flex items-center gap-1.5 truncate text-neutral-500 text-sm",
        className
      )}
      {...props}
    />
  );
}

export function BranchAttributeValue({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={classNames("text-neutral-700 text-sm", className)} {...props} />;
}
