import { DateDisplay } from "@/components/display/date-display";
import { Badge } from "@/components/ui/badge";
import { Icon } from "@iconify-icon/react";

type ProposedChangesInfoProps = {
  name: string;
  branch: string;
  date: string | number | Date | undefined;
  comments: number;
};

export const ProposedChangesInfo = ({ name, branch, date, comments }: ProposedChangesInfoProps) => {
  return (
    <div className="flex items-center gap-2">
      {/* <Icon icon={"mdi:file-check-outline"} /> */}

      <div className="flex flex-1 flex-col items-start">
        <div className="flex items-center gap-2">
          <span className="text-base">{name}</span>
          <Badge className="rounded-full">
            <Icon icon={"mdi:message-outline"} className="mr-1 " />
            {comments || "0"}
          </Badge>
        </div>

        <div className="flex items-center">
          <Badge className="mr-2">
            <Icon icon={"mdi:layers-triple"} className="mr-1" />
            {branch}
          </Badge>

          <div className="flex gap-1 text-gray-600">
            Opened <DateDisplay date={date} /> by Admin
          </div>
        </div>
      </div>
    </div>
  );
};
