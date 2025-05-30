import IpNamespaceSelector from "@/entities/ipam/ip-namespaces/ip-namespace-selector";
import { IpNamespaceProvider } from "@/entities/ipam/ip-namespaces/ui/ip-namespace-provider";
import { IpamBreadcrumb } from "@/entities/ipam/ipam-breadcrumb";
import IpamTree from "@/entities/ipam/ipam-tree/ipam-tree";
import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { Card } from "@/shared/components/ui/card";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { ErrorBoundary } from "react-error-boundary";
import { Outlet } from "react-router";

export const Component = () => {
  return (
    <IpNamespaceProvider>
      <Row className="items-stretch gap-0.5 h-full w-full overflow-hidden">
        <Card className="flex flex-col p-0 w-60 shrink-0">
          <IpNamespaceSelector className="border-b border-gray-200" />
          <ErrorBoundary fallbackRender={({ error }) => <ErrorScreen message={error.message} />}>
            <ScrollArea scrollX>
              <IpamTree className="w-full px-2" />
            </ScrollArea>
          </ErrorBoundary>
        </Card>

        <Col className="gap-0.5 overflow-hidden grow">
          <Card className="p-0 px-2 shrink-0">
            <IpamBreadcrumb />
          </Card>

          <Card className="flex flex-col p-0 grow overflow-hidden">
            <Outlet />
          </Card>
        </Col>
      </Row>
    </IpNamespaceProvider>
  );
};
