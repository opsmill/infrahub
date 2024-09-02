import { DateDisplay } from "@/components/display/date-display";
import { Badge } from "@/components/ui/badge";
import { Icon } from "@iconify-icon/react";
import { ReactComponent as PcCheckSuccess } from "@/images/icons/proposed-change-checks-success.svg";
import { ReactComponent as PcCheckFailure } from "@/images/icons/proposed-change-checks-failure.svg";
import { ReactComponent as PcCheckUnknown } from "@/images/icons/proposed-change-checks-unknown.svg";

type ProposedChangesInfoProps = {
  name: string;
  branch: string;
  date: string | number | Date | undefined;
  comments: number;
  checks: Array<{ conclusion: "success" | "failure" | "unknown" }>;
};

export const ProposedChangesInfo = ({
  name,
  branch,
  date,
  comments,
  checks,
}: ProposedChangesInfoProps) => {
  return (
    <>
      <CheckStatus checks={checks} />

      <div className="p-1 px-2 space-y-1 truncate">
        <div className="flex items-center gap-2">
          <span className="text-base font-medium">{name}</span>

          <Badge className="rounded-full font-normal">
            <Icon icon={"mdi:message-outline"} className="mr-1 mt-px" />
            {comments ?? 0}
          </Badge>
        </div>

        <div className="flex items-center gap-2">
          <Badge className="font-normal">
            <Icon icon={"mdi:layers-triple"} className="mr-1" /> {branch}
          </Badge>

          <div className="flex gap-1 text-gray-600">
            Opened <DateDisplay date={date} /> by Admin
          </div>
        </div>
      </div>
    </>
  );
};

const CheckStatus = ({
  checks,
  className,
}: {
  className?: string;
  checks: ProposedChangesInfoProps["checks"];
}) => {
  if (checks.length === 0) {
    return <PcCheckSuccess className={className} />;
  }

  if (checks.some(({ conclusion }) => conclusion === "failure")) {
    return <PcCheckFailure className={className} />;
  }

  if (checks.some(({ conclusion }) => conclusion === "unknown")) {
    return <PcCheckUnknown className={className} />;
  }

  return <PcCheckSuccess className={className} />;
};
