import IpNamespaceSelector from "@/entities/ipam/ip-namespace-selector";
import IpamTree from "@/entities/ipam/ipam-tree/ipam-tree";
import { IpNamespaceProvider } from "@/entities/ipam/namespaces/ui/ip-namespace-provider";
import { Col } from "@/shared/components/container";
import Content from "@/shared/components/layout/content";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { Outlet } from "react-router";

function IpamLayout() {
  return (
    <Content.Card className="flex h-full w-full">
      <IpNamespaceProvider>
        <Col className="w-60 shrink-0 border-r border-gray-200 h-full">
          <IpNamespaceSelector className="border-b border-gray-200" />
          <ScrollArea scrollX className="w-full p-2">
            <IpamTree className="w-full" />
          </ScrollArea>
        </Col>

        <section className="grow flex flex-col overflow-hidden">
          <Outlet />
        </section>
      </IpNamespaceProvider>
    </Content.Card>
  );
}

export const Component = IpamLayout;
