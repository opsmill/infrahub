import { Outlet } from "react-router-dom";

import { CardWithBorder } from "@/components/ui/card";
import Content from "@/screens/layout/content";
import IpNamespaceSelector from "../../screens/ipam/ip-namespace-selector";
import IpamTree from "../../screens/ipam/ipam-tree/ipam-tree";

function IpamLayout() {
  return (
    <>
      <Content.Title title="IP Address Manager">
        <IpNamespaceSelector />
      </Content.Title>

      <Content className="flex p-2 gap-2">
        <CardWithBorder contentClassName="p-2" className="min-w-64 max-w-[400px]">
          <IpamTree className="min-w-full" />
        </CardWithBorder>

        <section className="flex-grow">
          <Outlet />
        </section>
      </Content>
    </>
  );
}

export function Component() {
  return <IpamLayout />;
}
