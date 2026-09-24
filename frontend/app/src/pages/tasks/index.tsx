import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Link } from "@/shared/components/ui/link";

import { useGetTaskCount } from "@/entities/tasks/ui/queries/get-task-count.query";
import { TaskItems } from "@/entities/tasks/ui/task-items";

export function Component() {
  const { data: count, isPending, error } = useGetTaskCount();

  if (isPending) {
    return (
      <Content.Card className="h-full">
        <LoadingIndicator className="h-full" />
      </Content.Card>
    );
  }

  if (error) {
    return (
      <Content.Card className="h-full">
        <ErrorScreen message={error.message} />
      </Content.Card>
    );
  }

  return (
    <Content.Card>
      <Content.CardTitle title="Task Overview" badgeContent={count} />

      <div className="px-2 pt-2">
        <Link to="/tasks/scheduled">View scheduled flows</Link>
      </div>

      <TaskItems />
    </Content.Card>
  );
}
