import { useAtomValue } from "jotai";
import { Outlet, useParams } from "react-router-dom";
import ObjectHeader from "@/screens/objects/object-header";
import { genericsState, profilesAtom, schemaState } from "@/state/atoms/schema.atom";
import { HierarchicalTree } from "@/screens/objects/hierarchical-tree";

const ObjectPageLayout = () => {
  const { objectKind, objectid } = useParams();

  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);
  const profiles = useAtomValue(profilesAtom);

  const schema = [...nodes, ...generics, ...profiles].find(({ kind }) => kind === objectKind);

  if (!schema) return null;

  const isHierarchicalModel = "hierarchical" in schema && schema.hierarchical;
  const inheritFormHierarchicalModel = "hierarchy" in schema && schema.hierarchy;

  const treeSchema = isHierarchicalModel
    ? schema
    : inheritFormHierarchicalModel
    ? generics.find(({ kind }) => kind === schema.hierarchy)
    : null;

  return (
    <>
      <ObjectHeader schema={schema} objectId={objectid} />

      <div className="flex gap-2 p-2 overflow-auto">
        {treeSchema && (
          <HierarchicalTree
            className="w-full max-w-sm self-start"
            schema={treeSchema}
            currentNodeId={objectid}
          />
        )}

        <div className="flex-grow">
          <Outlet />
        </div>
      </div>
    </>
  );
};

export const Component = ObjectPageLayout;
