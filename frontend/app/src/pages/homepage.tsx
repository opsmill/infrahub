import Content from "@/shared/components/layout/content";

import { BranchesWidget } from "@/entities/homepage/ui/branches-widget";
import { EventsWidget } from "@/entities/homepage/ui/events-widget";
import { GettingStarted } from "@/entities/homepage/ui/getting-started";
import { GitRepositoriesWidget } from "@/entities/homepage/ui/git-repositories-widget";
import { ProposedChangesWidget } from "@/entities/homepage/ui/proposed-changes-widget";
import { TasksWidget } from "@/entities/homepage/ui/tasks-widget";

const Homepage = () => {
  return (
    <Content className="flex flex-col gap-4 p-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="col-span-2 flex flex-col gap-4">
          <ProposedChangesWidget className="max-h-[400px] min-h-80" />

          <BranchesWidget className="max-h-[400px] min-h-80" />
        </div>

        <div className="flex max-h-[816px] min-h-0 flex-col gap-4">
          <GitRepositoriesWidget className="max-h-1/3" />

          <EventsWidget />
        </div>
      </div>

      <TasksWidget className="min-h-[500px]" />

      <GettingStarted />
    </Content>
  );
};

export const Component = Homepage;
