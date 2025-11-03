import { GettingStarted } from "@/pages/home/getting-started";

import Content from "@/shared/components/layout/content";

const Homepage = () => {
  return (
    <Content className="p-4">
      <h1 className="pb-4 font-semibold text-2xl">Welcome to Infrahub!</h1>

      <GettingStarted />
    </Content>
  );
};

export function Component() {
  return <Homepage />;
}
