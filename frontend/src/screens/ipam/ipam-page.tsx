import { Outlet } from "react-router-dom";

import { Card } from "../../components/ui/card";
import Content from "../layout/content";
import IpamTree from "./ipam-tree/ipam-tree";

export default function IpamPage() {
  return (
    <>
      <Content.Title title="IP Address Manager" />

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
