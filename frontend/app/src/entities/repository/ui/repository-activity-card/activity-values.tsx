import { Tooltip } from "@infrahub/ui";

import { DateDisplay } from "@/shared/components/display/date-display";

const WORKER_ID_SHORT_LENGTH = 8;

export function ActivityTime({ date }: { date: string }) {
  return (
    <DateDisplay
      date={date}
      fullTimestamp
      containerClassName="inline-flex shrink-0"
      className="text-foreground-muted tabular-nums"
    />
  );
}

export function WorkerId({ id }: { id: string }) {
  return (
    <Tooltip message={`Worker ${id}`} nonInteractiveTrigger>
      <span className="font-mono">{id.slice(0, WORKER_ID_SHORT_LENGTH)}</span>
    </Tooltip>
  );
}
