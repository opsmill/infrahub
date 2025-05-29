import IpNamespaceSelector from "@/entities/ipam/ip-namespace-selector";
import IpamTree from "@/entities/ipam/ipam-tree/ipam-tree";
import { IpNamespaceProvider } from "@/entities/ipam/namespaces/ui/ip-namespace-provider";
import { Row } from "@/shared/components/container";
import { Card } from "@/shared/components/ui/card";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { Outlet } from "react-router";

function IpamLayout() {
  return (
    <IpNamespaceProvider>
      <Row className="items-stretch gap-0.5 h-full w-full overflow-hidden">
        <Card className="flex flex-col p-0 w-60 shrink-0">
          <IpNamespaceSelector className="border-b border-gray-200" />
          <ScrollArea scrollX>
            <IpamTree className="w-full px-2" />
          </ScrollArea>
        </Card>

        <Card className="flex flex-col p-0 grow overflow-hidden">
          <Outlet />
        </Card>
      </Row>
    </IpNamespaceProvider>
  );
}

export const Component = IpamLayout;
