import Accordion from "@/components/display/accordion";
import { DateDisplay } from "@/components/display/date-display";
import { Badge } from "@/components/ui/badge";
import { TASK_OBJECT } from "@/config/constants";
import { TASK_DETAILS } from "@/graphql/queries/tasks/getTasksItemDetails";
import useQuery from "@/hooks/useQuery";
import { classNames } from "@/utils/common";
import ErrorScreen from "../errors/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import { getSeverityBadge, tLog } from "../tasks/logs";

const background = {
  // Blue
  SCHEDULED: "bg-custom-blue-700/10",
  PENDING: "bg-custom-blue-700/10",
  RUNNING: "bg-custom-blue-700/10",
  PAUSED: "bg-custom-blue-700/10",
  CANCELLING: "bg-custom-blue-700/10",
  // Green
  COMPLETED: "bg-green-700/10",
  // Yellow
  CANCELLED: "bg-yellow-100",
  // Red
  FAILED: "bg-red-100",
  CRASHED: "bg-red-100",
};

export const getLogBadge: { [key: string]: any } = {
  // Blue
  SCHEDULED: <Badge variant={"blue-outline"}>SCHEDULED</Badge>,
  PENDING: <Badge variant={"blue-outline"}>PENDING</Badge>,
  RUNNING: <Badge variant={"blue-outline"}>RUNNING</Badge>,
  PAUSED: <Badge variant={"blue-outline"}>PAUSED</Badge>,
  CANCELLING: <Badge variant={"blue-outline"}>CANCELLING</Badge>,
  // Green
  COMPLETED: <Badge variant={"green-outline"}>COMPLETED</Badge>,
  // Yellow
  CANCELLED: <Badge variant={"yellow-outline"}>CANCELLED</Badge>,
  // Red
  FAILED: <Badge variant={"red-outline"}>FAILED</Badge>,
  CRASHED: <Badge variant={"red-outline"}>CRASHED</Badge>,
};

function Task({ task }) {
  return (
    <div>
      <div
        className={classNames(
          "flex flex-col gap-4 rounded-md p-4 m-auto",
          "bg-gray-100",
          background[task.state]
        )}
      >
        <div className="flex justify-between">
          <div className="flex items-center gap-4">
            {getLogBadge[task.state] ?? <Badge variant={"gray-outline"}>UNKOWN</Badge>}
            {task.title}
          </div>

          <DateDisplay date={task.updated_at} />
        </div>

        {!!task?.logs?.edges?.length && (
          <Accordion title={<div className="font-normal text-xs">Logs</div>}>
            <div className="flex flex-col gap-2 mt-2">
              {task?.logs?.edges?.map((edge, index) => (
                <Log key={index} {...edge.node} />
              ))}
            </div>
          </Accordion>
        )}
      </div>
    </div>
  );
}

interface TaskDisplayProps {
  branch?: string;
  workflow?: Array<string>;
  relatedNode?: string;
}

export function TaskDisplay({ branch, workflow, relatedNode }: TaskDisplayProps) {
  const { loading, error, data } = useQuery(TASK_DETAILS, {
    variables: {
      branch,
      workflow,
      relatedNodes: relatedNode ? [relatedNode] : undefined,
    },
    pollInterval: 5000,
  });

  if (error) {
    return <ErrorScreen message="An error occured while retrieving the task details." />;
  }

  if (loading) {
    return <LoadingScreen message={"Loading task..."} />;
  }

  return (
    <div className="flex flex-col gap-2 overflow-scroll">
      {data[TASK_OBJECT].edges?.map((edge, index) => (
        <Task key={index} task={edge.node} />
      ))}
    </div>
  );
}

function Log({ message, severity, timestamp }: tLog) {
  return (
    <div className="flex flex-col bg-white rounded-md p-4 gap-2">
      <div className="flex items-center justify-between">
        {getSeverityBadge[severity]}
        <DateDisplay date={timestamp} />
      </div>

      <pre className="text-xs">{message}</pre>
    </div>
  );
}
