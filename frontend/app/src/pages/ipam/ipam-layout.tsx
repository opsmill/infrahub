import { SidebarIcon } from "lucide-react";
import { ErrorBoundary } from "react-error-boundary";
import { Outlet } from "react-router";

import { IPAM_TREE_KEY } from "@/config/localStorage";

import { Separator } from "@/shared/components/aria/separator";
import { Button } from "@/shared/components/buttons/button-primitive";
import { Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/shared/components/ui/resizable";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { useLocalStorage } from "@/shared/hooks/useLocalStorage";

import IpNamespaceSelector from "@/entities/ipam/ip-namespaces/ip-namespace-selector";
import { IpNamespaceProvider } from "@/entities/ipam/ip-namespaces/ui/ip-namespace-provider";
import IpamTree from "@/entities/ipam/ipam-tree/ipam-tree";

export const Component = () => {
  const [collapsed, setCollapsed] = useLocalStorage(IPAM_TREE_KEY);

  const booleanCollapsed = collapsed === "true";

  return (
    <IpNamespaceProvider>
      <ResizablePanelGroup direction="horizontal" className="items-stretch">
        <ResizablePanel defaultSize={20} minSize={10} maxSize={50} className="flex grow flex-col">
          <Content.Card className="flex grow flex-col">
            <Row className="h-11 gap-0">
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

              <IpNamespaceSelector className="m-0.75 grow" />
            </Row>

            <Separator />

            <ErrorBoundary fallbackRender={({ error }) => <ErrorScreen message={error.message} />}>
              <ScrollArea scrollX>
                <IpamTree className="w-full px-2" />
              </ScrollArea>
            </ErrorBoundary>
          </Content.Card>
        </ResizablePanel>

        <ResizableHandle />

        <ResizablePanel className="flex grow flex-col">
          <Content.Card className="flex grow flex-col">
            <Outlet />
          </Content.Card>
        </ResizablePanel>
      </ResizablePanelGroup>
    </IpNamespaceProvider>
  );
};
