import Content from "@/shared/components/layout/content";

import { Branches } from "@/entities/homepage/ui/branches";
import { GettingStarted } from "@/entities/homepage/ui/getting-started";
import { GitRepositories } from "@/entities/homepage/ui/git-repositories";
import { ProposedChanges } from "@/entities/homepage/ui/proposed-changes";

const Homepage = () => {
  return (
    <Content className="flex flex-col gap-4 p-4">
      <h1 className="font-semibold text-2xl">Welcome to Infrahub!</h1>

      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 flex flex-col gap-4">
          <ProposedChanges className="h-80" />

          <Branches />
        </div>

        <GitRepositories className="h-44" />
      </div>

      <GettingStarted />
    </Content>
  );
};

export const Component = Homepage;
