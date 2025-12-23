import { Outlet, useLocation, useParams } from "react-router";

import NoDataFound from "@/shared/components/errors/no-data-found";
import Content from "@/shared/components/layout/content";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/shared/components/ui/resizable";
import { ScrollArea } from "@/shared/components/ui/scroll-area";

import { ObjectHierarchyTreeWrapper } from "@/entities/nodes/hierarchy/ui/object-hierarchy-tree-wrapper";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { getGenericSchemaOfHierarchy } from "@/entities/schema/utils/is-hierarchical-schema";

const ObjectPageLayout = () => {
  const { objectKind, objectId } = useParams();
  const location = useLocation();
  const { schema } = useSchema(objectKind);

  if (!schema) return <NoDataFound message={`No schema found for ${objectKind}`} />;

  const genericSchemaOfHierarchy = getGenericSchemaOfHierarchy(schema);
  const isConvertPage = location.pathname.includes("/convert");

  if (!genericSchemaOfHierarchy || isConvertPage) {
    return <Outlet />;
  }

  return (
    <ResizablePanelGroup className="items-stretch overflow-hidden">
      <ResizablePanel defaultSize={300} minSize={40} maxSize="90%" className="flex grow flex-col">
        <Content.Card className="flex grow flex-col">
          <ScrollArea scrollX className="h-full p-1">
            <ObjectHierarchyTreeWrapper
              key={genericSchemaOfHierarchy.kind}
              treeSchema={genericSchemaOfHierarchy}
              currentNodeId={objectId}
            />
          </ScrollArea>
        </Content.Card>
      </ResizablePanel>

      <ResizableHandle />

      <ResizablePanel className="flex grow flex-col">
        <Outlet />
      </ResizablePanel>
    </ResizablePanelGroup>
  );
};

export const Component = ObjectPageLayout;
