import { Avatar, AVATAR_SIZE } from "@/components/display/avatar";
import { Tooltip } from "@/components/ui/tooltip";
import { Icon } from "@iconify-icon/react";

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
          <Tooltip message={reviewer.display_label}>
            <>
              <Avatar size={AVATAR_SIZE.SMALL} name={reviewer.display_label} />
              {approversId.includes(reviewer.id) && (
                <Icon
                  icon={"mdi:check"}
                  className="text-green-500 absolute -right-0.5 -bottom-0.5 bg-white rounded-full border border-green-500"
                />
              )}
            </>
          </Tooltip>
        </div>
      ))}
    </div>
  );
};
