import IpNamespaceSelector from "@/entities/ipam/ip-namespace-selector";
import IpamTree from "@/entities/ipam/ipam-tree/ipam-tree";
import Content from "@/shared/components/layout/content";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { Outlet } from "react-router";

function IpamLayout() {
  return (
    <Content.Card className="h-[calc(100%-1rem)] flex flex-col overflow-hidden">
      <Content.Title title={<h1>IP Address Manager</h1>}>
        <IpNamespaceSelector />
      </Content.Title>

      <div className="grow flex overflow-auto">
        <div className="min-w-64 max-w-[400px] border-r border-gray-200 flex">
          <ScrollArea scrollX className="w-full p-2">
            <IpamTree className="w-full" />
          </ScrollArea>
        </div>

        <section className="grow overflow-auto">
          <Outlet />
        </section>
      </div>
    </Content.Card>
  );
}

export const Component = IpamLayout;
