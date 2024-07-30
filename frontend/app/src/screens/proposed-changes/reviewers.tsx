import { Avatar } from "@/components/display/avatar";
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
                  className="text-green-700 absolute -right-[4px] -bottom-[4px] bg-green-300 rounded-full border border-white"
                  data-test-id="approved-icon"
                />
              )}
            </>
          </Tooltip>
        </div>
      ))}
    </div>
  );
};
