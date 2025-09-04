import { Icon } from "@iconify-icon/react";

import { Avatar } from "@/shared/components/display/avatar";
import { Tooltip } from "@/shared/components/ui/tooltip";

type ProposedChangesReviewersProps = {
  reviewers: any[];
  approved_by: any[];
};

export const ProposedChangesReviewers = ({
  reviewers,
  approved_by,
}: ProposedChangesReviewersProps) => {
  if (!reviewers.length) return <span className="italic">No reviewers</span>;

  const approversId = approved_by.map((node) => node.id);

  return (
    <div className="flex gap-1">
      {reviewers.map((reviewer: any, index: number) => (
        <div className="relative" key={index}>
          <Tooltip content={reviewer.display_label}>
            <>
              <Avatar
                size="sm"
                variant={approversId.includes(reviewer.id) ? "active" : "primary"}
                name={reviewer.display_label}
              />
              {approversId.includes(reviewer.id) && (
                <Icon
                  icon={"mdi:check"}
                  className="-right-[4px] -bottom-[4px] absolute rounded-full border border-white bg-green-300 text-green-700"
                  data-testid="approved-icon"
                />
              )}
            </>
          </Tooltip>
        </div>
      ))}
    </div>
  );
};
