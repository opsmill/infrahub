import { Outlet } from "react-router-dom";

import { Card } from "../../components/ui/card";
import Content from "../layout/content";
import IpamTree from "./ipam-tree/ipam-tree";
import NamespaceSelector from "./namespace-selector";

export default function IpamPage() {
  return (
    <>
      <Content.Title>
        <div className="flex items-center">
          <h3 className="font-semibold text-sm mr-3">IP Address Manager</h3>

          <NamespaceSelector />
        </div>
      </Content.Title>

      <Content className="flex p-2 gap-2">
        <Card className="overflow-auto">
          <IpamTree />
        </Card>

        <section className="flex-grow">
          <Outlet />
        </section>
      </Content>
    </>
  );
}
