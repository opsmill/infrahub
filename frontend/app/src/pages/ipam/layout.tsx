import { ScrollArea } from "@/components/ui/scroll-area";
import Content from "@/screens/layout/content";
import { Outlet } from "react-router-dom";
import IpNamespaceSelector from "../../screens/ipam/ip-namespace-selector";
import IpamTree from "../../screens/ipam/ipam-tree/ipam-tree";

function IpamLayout() {
  return (
    <Content.Card className="h-[calc(100%-1rem)] flex flex-col overflow-hidden">
      <Content.Title title={<h1>IP Address Manager</h1>}>
        <IpNamespaceSelector />
      </Content.Title>

      <div className="flex-grow flex overflow-auto">
        <div className="min-w-64 max-w-[400px] border-r flex">
          <ScrollArea className="w-full p-2">
            <IpamTree className="w-full" />
          </ScrollArea>
        </div>

        <section className="flex-grow overflow-auto">
          <Outlet />
        </section>
      </div>
    </Content.Card>
  );
}

export function Component() {
  return <IpamLayout />;
}
