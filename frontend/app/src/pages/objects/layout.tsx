import { ScrollArea } from "@/components/ui/scroll-area";
import NoDataFound from "@/screens/errors/no-data-found";
import Content from "@/screens/layout/content";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { HierarchicalTree } from "@/screens/objects/hierarchical-tree";
import ObjectHeader from "@/screens/objects/object-header";
import { genericsState, profilesAtom, schemaState } from "@/state/atoms/schema.atom";
import { stateAtom } from "@/state/atoms/state.atom";
import { useAtomValue } from "jotai";
import { Outlet, useParams } from "react-router-dom";

const ObjectPageLayout = () => {
  const { objectKind, objectid } = useParams();

  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);
  const profiles = useAtomValue(profilesAtom);
  const state = useAtomValue(stateAtom);
  const schema = [...nodes, ...generics, ...profiles].find(({ kind }) => kind === objectKind);

  if (!state.isReady) {
    return (
      <Content.Card className="flex justify-center items-center p-5 min-h-[400px]">
        <LoadingScreen message="Loading schema..." />
      </Content.Card>
    );
  }

  if (!schema) return <NoDataFound message="No schema found for this kind." />;

  const isHierarchicalModel = "hierarchical" in schema && schema.hierarchical;
  const inheritFormHierarchicalModel = "hierarchy" in schema && schema.hierarchy;

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
    <Content.Card>
      <ObjectHeader schema={schema} objectId={objectid} />

      <div className="flex-grow flex overflow-auto">
        {treeSchema && (
          <ScrollArea className="min-w-64 max-w-[400px] border-r">
            <HierarchicalTree
              schema={treeSchema}
              currentNodeId={objectid}
              className="p-2 min-w-full"
            />
          </ScrollArea>
        )}

        <div className="flex-grow overflow-auto">
          <Outlet />
        </div>
      </div>
    </Content.Card>
  );
};

export const Component = ObjectPageLayout;
