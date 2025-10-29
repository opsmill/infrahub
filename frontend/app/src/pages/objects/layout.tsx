import { useAtomValue } from "jotai";
import { Outlet, useParams } from "react-router";

import NoDataFound from "@/shared/components/errors/no-data-found";
import Content from "@/shared/components/layout/content";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/shared/components/ui/resizable";
import { ScrollArea } from "@/shared/components/ui/scroll-area";

import { ObjectHierarchyTreeWrapper } from "@/entities/nodes/hierarchy/ui/object-hierarchy-tree-wrapper";
import ObjectHeader from "@/entities/nodes/object-header";
import { genericSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

const ObjectPageLayout = () => {
  const { objectKind, objectid } = useParams();

  const generics = useAtomValue(genericSchemasAtom);
  const { schema } = useSchema(objectKind);

  if (!schema) return <NoDataFound message={`No schema found for ${objectKind}`} />;

  const isHierarchicalModel = "hierarchical" in schema && schema.hierarchical;
  const inheritFormHierarchicalModel = "hierarchy" in schema && schema.hierarchy;

  if (isHierarchicalModel || inheritFormHierarchicalModel) {
    const getTreeSchema = () => {
      if (isHierarchicalModel) {
        return schema;
      }

      if (inheritFormHierarchicalModel) {
        return generics.find(({ kind }) => kind === schema.hierarchy);
      }

      return null;
    };

    const treeSchema = getTreeSchema();

    return (
      <ResizablePanelGroup direction="horizontal" className="items-stretch">
        {treeSchema && (
          <>
            <ResizablePanel
              defaultSize={20}
              minSize={10}
              maxSize={50}
              className="flex grow flex-col"
            >
              <Content.Card className="flex grow flex-col">
                <ScrollArea scrollX className="h-full p-1">
                  <ObjectHierarchyTreeWrapper treeSchema={treeSchema} currentNodeId={objectid} />
                </ScrollArea>
              </Content.Card>
            </ResizablePanel>

            <ResizableHandle withHandle className="w-0.5 bg-transparent" />
          </>
        )}

        <ResizablePanel className="flex grow flex-col">
          <Content.Card className="flex grow flex-col">
            <ObjectHeader schema={schema} objectId={objectid} />

            <Outlet />
          </Content.Card>
        </ResizablePanel>
      </ResizablePanelGroup>
    );
  }

  return (
    <Content.Card className="flex flex-col">
      <ObjectHeader schema={schema} objectId={objectid} />

      <Outlet />
    </Content.Card>
  );
};

export const Component = ObjectPageLayout;
