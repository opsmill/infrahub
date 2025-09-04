import { SidebarIcon } from "lucide-react";
import { ErrorBoundary } from "react-error-boundary";
import { Outlet } from "react-router";

import { IPAM_TREE_KEY } from "@/config/localStorage";

import { Separator } from "@/shared/components/aria/separator";
import { Button } from "@/shared/components/buttons/button-primitive";
import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { Card } from "@/shared/components/ui/card";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { useLocalStorage } from "@/shared/hooks/useLocalStorage";

import IpNamespaceSelector from "@/entities/ipam/ip-namespaces/ip-namespace-selector";
import { IpNamespaceProvider } from "@/entities/ipam/ip-namespaces/ui/ip-namespace-provider";
import { IpamBreadcrumb } from "@/entities/ipam/ipam-breadcrumb";
import IpamTree from "@/entities/ipam/ipam-tree/ipam-tree";

export const Component = () => {
  const [collapsed, setCollapsed] = useLocalStorage(IPAM_TREE_KEY);

  const booleanCollapsed = collapsed === "true";

  return (
    <IpNamespaceProvider>
      <Card className="p-0 flex flex-col size-full overflow-hidden">
        <Row className="h-11 gap-0 *:shrink-0">
          <Button
            variant="ghost"
            size="square"
            aria-label="toggle IPAM tree"
            onClick={() => setCollapsed(JSON.stringify(!booleanCollapsed))}
            className="m-1 text-gray-400 hover:text-neutral-600"
          >
            <SidebarIcon className="size-4" />
          </Button>
          <Separator orientation="vertical" />
          <IpNamespaceSelector className="w-47 m-0.75" />
          <Separator orientation="vertical" />
          <IpamBreadcrumb className="grow px-2" />
        </Row>

        <Separator />

        <Row className="items-stretch overflow-hidden gap-0 grow">
          {!booleanCollapsed && (
            <Col className="gap-0 w-60 shrink-0 border-r border-gray-200">
              <ErrorBoundary
                fallbackRender={({ error }) => <ErrorScreen message={error.message} />}
              >
                <ScrollArea scrollX>
                  <IpamTree className="w-full px-2" />
                </ScrollArea>
              </ErrorBoundary>
            </Col>
          )}

          <Col className="gap-0 grow overflow-hidden">
            <Outlet />
          </Col>
        </Row>
      </Card>
    </IpNamespaceProvider>
  );
};
