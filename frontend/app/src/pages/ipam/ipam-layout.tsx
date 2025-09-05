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
      <Card className="flex size-full flex-col overflow-hidden p-0">
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
          <IpNamespaceSelector className="m-0.75 w-47" />
          <Separator orientation="vertical" />
          <IpamBreadcrumb className="grow px-2" />
        </Row>

        <Separator />

        <Row className="grow items-stretch gap-0 overflow-hidden">
          {!booleanCollapsed && (
            <Col className="w-60 shrink-0 gap-0 border-gray-200 border-r">
              <ErrorBoundary
                fallbackRender={({ error }) => <ErrorScreen message={error.message} />}
              >
                <ScrollArea scrollX>
                  <IpamTree className="w-full px-2" />
                </ScrollArea>
              </ErrorBoundary>
            </Col>
          )}

          <Col className="grow gap-0 overflow-hidden">
            <Outlet />
          </Col>
        </Row>
      </Card>
    </IpNamespaceProvider>
  );
};
