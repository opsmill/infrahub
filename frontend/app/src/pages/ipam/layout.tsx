import IpNamespaceSelector from "@/entities/ipam/ip-namespace-selector";
import IpamTree from "@/entities/ipam/ipam-tree/ipam-tree";
import { IpNamespaceProvider } from "@/entities/ipam/namespaces/ui/ip-namespace-provider";
import { Col } from "@/shared/components/container";
import Content from "@/shared/components/layout/content";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { Outlet } from "react-router";

function IpamLayout() {
  return (
    <Content.Card className="h-[calc(100%-1rem)] flex">
      <IpNamespaceProvider>
        <Col className="min-w-64 max-w-[400px] gap-0 border-r border-gray-200 shrink-0">
          <IpNamespaceSelector className="border-b border-gray-200" />
          <ScrollArea scrollX className="w-full p-2">
            <IpamTree className="w-full" />
          </ScrollArea>
        </Col>

        <section className="flex flex-col h-full grow">
          <Outlet />
        </section>
      </IpNamespaceProvider>
    </Content.Card>
  );
}

export const Component = IpamLayout;
