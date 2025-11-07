import { useAtom, useAtomValue } from "jotai";
import { atomWithStorage } from "jotai/utils";
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
import { classNames } from "@/shared/utils/common";

import IpNamespaceSelector from "@/entities/ipam/ip-namespaces/ip-namespace-selector";
import { IpNamespaceProvider } from "@/entities/ipam/ip-namespaces/ui/ip-namespace-provider";
import IpamTree from "@/entities/ipam/ipam-tree/ipam-tree";

const ipamTreeCollapsedAtom = atomWithStorage(IPAM_TREE_KEY, false);

export const Component = () => {
  const ipamTreeCollapsed = useAtomValue(ipamTreeCollapsedAtom);

  return (
    <IpNamespaceProvider>
      <ResizablePanelGroup direction="horizontal" className="items-stretch">
        {!ipamTreeCollapsed && (
          <>
            <ResizablePanel
              defaultSize={20}
              minSize={10}
              maxSize={50}
              className="flex grow flex-col"
            >
              <Content.Card className="flex grow flex-col">
                <IpamToolbar />

                <ErrorBoundary
                  fallbackRender={({ error }) => <ErrorScreen message={error.message} />}
                >
                  <ScrollArea scrollX>
                    <IpamTree className="w-full px-2" />
                  </ScrollArea>
                </ErrorBoundary>
              </Content.Card>
            </ResizablePanel>

            <ResizableHandle />
          </>
        )}

        <ResizablePanel className="flex grow flex-col">
          <Content.Card className="flex grow flex-col">
            {ipamTreeCollapsed && <IpamToolbar />}
            <Outlet />
          </Content.Card>
        </ResizablePanel>
      </ResizablePanelGroup>
    </IpNamespaceProvider>
  );
};

function IpamToolbar() {
  const [collapsed, setCollapsed] = useAtom(ipamTreeCollapsedAtom);

  return (
    <>
      <Row className="h-11 gap-0">
        <Button
          variant="ghost"
          size="square"
          aria-label="toggle IPAM tree"
          onClick={() => setCollapsed(!collapsed)}
          className="m-1 text-gray-400 hover:text-neutral-600"
        >
          <SidebarIcon className="size-4" />
        </Button>

        <Separator orientation="vertical" />

        <IpNamespaceSelector className={classNames("m-0.75 grow", collapsed && "max-w-[313px]")} />
      </Row>

      <Separator />
    </>
  );
}
