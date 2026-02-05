import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { TASK_OBJECT } from "@/shared/config/constants";

import { useObjectsCount } from "@/entities/nodes/object/domain/get-objects-count.query";
import { TaskItems } from "@/entities/tasks/ui/task-items";

export function Component() {
  const { data: count, isPending, error } = useObjectsCount({ objectKind: TASK_OBJECT });

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
      <TaskItems />
    </Content.Card>
  );
}
