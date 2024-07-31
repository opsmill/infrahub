import { useAtomValue } from "jotai";
import { Outlet, useParams } from "react-router-dom";
import ObjectHeader from "@/screens/objects/object-header";
import { genericsState, profilesAtom, schemaState } from "@/state/atoms/schema.atom";
import { HierarchicalTree } from "@/screens/objects/hierarchical-tree";
import NoDataFound from "@/screens/errors/no-data-found";
import { stateAtom } from "@/state/atoms/state.atom";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { CardWithBorder } from "@/components/ui/card";

const ObjectPageLayout = () => {
  const { objectKind, objectid } = useParams();

  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);
  const profiles = useAtomValue(profilesAtom);
  const state = useAtomValue(stateAtom);
  const schema = [...nodes, ...generics, ...profiles].find(({ kind }) => kind === objectKind);

  if (!state.isReady)
    return (
      <div className="flex flex-1 items-center justify-center">
        <LoadingScreen message="Loading schema..." />
      </div>
    );

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
    <>
      <ObjectHeader schema={schema} objectId={objectid} />

      <div className="flex-grow flex gap-2 p-2 overflow-auto">
        {treeSchema && (
          <CardWithBorder className="min-w-64 max-w-[400px]">
            <HierarchicalTree
              schema={treeSchema}
              currentNodeId={objectid}
              className="p-2 min-w-full"
            />
          </CardWithBorder>
        )}

        <div className="flex-grow">
          <Outlet />
        </div>
      </div>
    </>
  );
};

export const Component = ObjectPageLayout;
