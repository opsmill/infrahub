import { HierarchicalTree } from "@/entities/nodes/hierarchical-tree";
import ObjectHeader from "@/entities/nodes/object-header";
import { genericSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import NoDataFound from "@/shared/components/errors/no-data-found";
import Content from "@/shared/components/layout/content";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/shared/components/ui/resizable";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { useAtomValue } from "jotai";
import { Outlet, useParams } from "react-router";

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
      <Content.Card className="flex flex-col">
        <ObjectHeader schema={schema} objectId={objectid} />

        <ResizablePanelGroup direction="horizontal">
          {treeSchema && (
            <>
              <ResizablePanel defaultSize={20} minSize={10} maxSize={50}>
                <ScrollArea scrollX className="h-full">
                  <HierarchicalTree
                    schema={treeSchema}
                    currentNodeId={objectid}
                    className="p-2 min-w-full"
                  />
                </ScrollArea>
              </ResizablePanel>
              <ResizableHandle withHandle />
            </>
          )}

          <ResizablePanel>
            <ScrollArea scrollX className="h-full">
              <Outlet />
            </ScrollArea>
          </ResizablePanel>
        </ResizablePanelGroup>
      </Content.Card>
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
