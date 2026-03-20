import { useAtom, useAtomValue } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { SidebarIcon } from "lucide-react";
import { ErrorBoundary } from "react-error-boundary";
import { Outlet } from "react-router";

import { Separator } from "@/shared/components/aria/separator";
import { Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { Button } from "@/shared/components/ui/button";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/shared/components/ui/resizable";
import { classNames } from "@/shared/utils/common";

import { IPAM_TREE_KEY } from "@/entities/ipam/constants";
import { IpNamespaceProvider } from "@/entities/ipam/ip-namespaces/ui/ip-namespace-provider";
import IpNamespaceSelector from "@/entities/ipam/ip-namespaces/ui/ip-namespace-selector";
import { IpamTreeWithSearch } from "@/entities/ipam/ipam-tree/ui/ipam-tree-with-search";

const ipamTreeCollapsedAtom = atomWithStorage(IPAM_TREE_KEY, false);

export const Component = () => {
  const ipamTreeCollapsed = useAtomValue(ipamTreeCollapsedAtom);

  return (
    <IpNamespaceProvider>
      <ResizablePanelGroup orientation="horizontal" className="overflow-hidden">
        {!ipamTreeCollapsed && (
          <>
            <ResizablePanel
              id="tree-panel"
              defaultSize={300}
              minSize={40}
              maxSize="90%"
              className="flex grow flex-col"
            >
              <Content.Card className="flex grow flex-col">
                <IpamToolbar />

                <ErrorBoundary
                  fallbackRender={({ error }) => <ErrorScreen message={error.message} />}
                >
                  <IpamTreeWithSearch />
                </ErrorBoundary>
              </Content.Card>
            </ResizablePanel>

            <ResizableHandle />
          </>
        )}

        <ResizablePanel id="main-panel" className="flex grow flex-col">
          <Content.Card className="flex grow flex-col">
            {ipamTreeCollapsed && <IpamToolbar className="max-w-74.5" />}
            <Outlet />
          </Content.Card>
        </ResizablePanel>
      </ResizablePanelGroup>
    </IpNamespaceProvider>
  );
};

function IpamToolbar({ className }: { className?: string }) {
  const [collapsed, setCollapsed] = useAtom(ipamTreeCollapsedAtom);

  return (
    <>
      <Row className={classNames("h-11 gap-0", className)}>
        <Button
          variant="ghost"
          size="square"
          aria-label="toggle IPAM tree"
          onClick={() => setCollapsed(!collapsed)}
          className="m-1 shrink-0 rounded-lg text-gray-400 hover:text-neutral-600"
        >
          <SidebarIcon className="size-4" />
        </Button>

        <Separator orientation="vertical" />

        <IpNamespaceSelector className="m-0.5 grow" />
      </Row>

      <Separator />
    </>
  );
}
