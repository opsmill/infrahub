import Content from "@/shared/components/layout/content";

import { GettingStarted } from "@/entities/homepage/ui/getting-started";
import { GitRepositories } from "@/entities/homepage/ui/git-repositories";

const Homepage = () => {
  return (
    <Content className="flex flex-col gap-4 p-4">
      <h1 className="font-semibold text-2xl">Welcome to Infrahub!</h1>

      <div className="grid grid-cols-3">
        <div className="col-span-2 max-h-44" />

        <GitRepositories className="h-44" />
      </div>

      <GettingStarted />
    </Content>
  );
};

export const Component = Homepage;
