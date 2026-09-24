import Content from "@/shared/components/layout/content";
import { Link } from "@/shared/components/ui/link";

import { ScheduledFlowItems } from "@/entities/scheduled-flows/ui/scheduled-flow-items";

export function Component() {
  return (
    <Content.Card>
      <Content.CardTitle title="Scheduled Flows" />

      <div className="px-2 pt-2">
        <Link to="/tasks">Back to all tasks</Link>
      </div>

      <ScheduledFlowItems />
    </Content.Card>
  );
}
