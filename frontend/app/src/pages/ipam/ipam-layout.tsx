import IpNamespaceSelector from "@/entities/ipam/ip-namespaces/ip-namespace-selector";
import { IpNamespaceProvider } from "@/entities/ipam/ip-namespaces/ui/ip-namespace-provider";
import { IpamBreadcrumb } from "@/entities/ipam/ipam-breadcrumb";
import IpamTree from "@/entities/ipam/ipam-tree/ipam-tree";
import { Col } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { Card } from "@/shared/components/ui/card";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { ErrorBoundary } from "react-error-boundary";
import { Outlet } from "react-router";

export const Component = () => {
  return (
    <IpNamespaceProvider>
      <Card className="p-0 flex items-stretch h-full w-full overflow-hidden">
        <Col className="gap-0 w-60 shrink-0 border-r border-gray-200">
          <IpNamespaceSelector className="border-b border-gray-200 h-12" />

          <ErrorBoundary fallbackRender={({ error }) => <ErrorScreen message={error.message} />}>
            <ScrollArea scrollX>
              <IpamTree className="w-full px-2" />
            </ScrollArea>
          </ErrorBoundary>
        </Col>

        <Col className="gap-0 grow overflow-hidden">
          <IpamBreadcrumb className="h-12 shrink-0 border-b border-gray-200 px-2" />

          <Outlet />
        </Col>
      </Card>
    </IpNamespaceProvider>
  );
};
