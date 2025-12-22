import Content from "@/shared/components/layout/content";

import { BranchesWidget } from "@/entities/homepage/ui/branches-widget";
import { EventsWidget } from "@/entities/homepage/ui/events-widget";
import { GettingStarted } from "@/entities/homepage/ui/getting-started";
import { GitRepositoriesWidget } from "@/entities/homepage/ui/git-repositories-widget";
import { ProposedChangesWidget } from "@/entities/homepage/ui/proposed-changes-widget";
import { TasksWidget } from "@/entities/homepage/ui/tasks-widget";
import { useDashboardPlugins } from "@/entities/plugins/hooks/use-plugins";
import { PluginDashboardWidget } from "@/entities/plugins/ui/plugin-dashboard-widget";

const Homepage = () => {
  const dashboardPlugins = useDashboardPlugins();

  return (
    <Content className="grid auto-rows-[10rem] gap-3 p-3 lg:grid-cols-3">
      <ProposedChangesWidget className="col-span-1 row-span-2 lg:col-span-2" />
      <GitRepositoriesWidget className="col-span-1 row-span-1" />
      <BranchesWidget className="col-span-1 row-span-2 lg:col-span-2" />
      <EventsWidget className="col-span-1 row-span-3 lg:col-start-3 lg:row-start-2" />
      <TasksWidget className="col-span-full row-span-4 lg:row-span-3" />

      {/* Dashboard plugins */}
      {dashboardPlugins.map((plugin) => (
        <PluginDashboardWidget key={plugin.manifest.id} plugin={plugin} />
      ))}

      <GettingStarted className="col-span-full h-fit" />
    </Content>
  );
};

export const Component = Homepage;
