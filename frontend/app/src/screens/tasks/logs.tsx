import { DateDisplay } from "@/components/display/date-display";
import { Table } from "@/components/table/table";
import { Badge } from "@/components/ui/badge";

export type tLog = {
  id: string;
  message: string;
  severity: string;
  timestamp: string;
};

type LogsProps = {
  logs: tLog[];
};

export const getSeverityBadge: { [key: string]: any } = {
  success: <Badge variant={"green"}>success</Badge>,
  info: <Badge variant={"yellow"}>info</Badge>,
  warning: <Badge variant={"yellow"}>warning</Badge>,
  error: <Badge variant={"red"}>error</Badge>,
  critical: <Badge variant={"red"}>critical</Badge>,
};

export const Logs = ({ logs }: LogsProps) => {
  const columns = [
    {
      name: "message",
      label: "Message",
    },
    {
      name: "severity",
      label: "Severity",
    },
    {
      name: "timestamp",
      label: "Timestamp",
    },
  ];

  const rows = logs.map((log: tLog) => ({
    values: {
      ...log,
      severity: getSeverityBadge[log.severity],
      timestamp: <DateDisplay date={log.timestamp} />,
    },
  }));

  return (
    <div className="">
      <Table columns={columns} rows={rows} />
    </div>
  );
};
