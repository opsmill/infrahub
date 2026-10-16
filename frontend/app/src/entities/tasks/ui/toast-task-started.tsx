import { ArrowUpRightIcon } from "lucide-react";
import { toast } from "react-toastify";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Link } from "@/shared/components/ui/link";

import { getTaskDetailsUrl } from "@/entities/tasks/ui/routing/task-urls";

export function toastTaskStarted(startedMessage: string, taskId?: string) {
  const message = taskId ? (
    <>
      {startedMessage}
      <br />
      <Link to={getTaskDetailsUrl(taskId)} className="inline-flex items-center gap-1 underline">
        View task <ArrowUpRightIcon className="size-3.5" />
      </Link>
    </>
  ) : (
    `${startedMessage} You can view its status on the "Tasks" tab.`
  );
  toast(<Alert type={ALERT_TYPES.SUCCESS} message={message} />);
}
