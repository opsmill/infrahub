import { BADGE_TYPES, Badge } from "../../components/display/badge";
import { Table } from "../../components/table/table";

export type tLog = {
  id: string;
  message: string;
  severity: string;
  timestamp: string;
};

type tLogsProps = {
  logs: tLog[];
};

export const getSeverityBadge: { [key: string]: any } = {
  success: <Badge type={BADGE_TYPES.VALIDATE}>success</Badge>,
  info: <Badge type={BADGE_TYPES.LIGHT}>info</Badge>,
  warning: <Badge type={BADGE_TYPES.WARNING}>warning</Badge>,
  error: <Badge type={BADGE_TYPES.CANCEL}>error</Badge>,
  critical: <Badge type={BADGE_TYPES.CANCEL}>critical</Badge>,
};

export const Logs = (props: tLogsProps) => {
  const { logs } = props;

  const columns = [
    {
      name: "id",
      label: "ID",
    },
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
    },
  }));

  console.log("rows: ", rows);
  return (
    <div className="">
      <Table columns={columns} rows={rows} />
    </div>
  );
};
