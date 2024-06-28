import { useAtomValue } from "jotai";
import { Outlet, useParams } from "react-router-dom";
import ObjectHeader from "@/screens/objects/object-header";
import { genericsState, profilesAtom, schemaState } from "@/state/atoms/schema.atom";

const ObjectPageLayout = () => {
  const { objectKind, objectid } = useParams();

  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);
  const profiles = useAtomValue(profilesAtom);

  const schema = [...nodes, ...generics, ...profiles].find(({ kind }) => kind === objectKind);

  if (!schema) return null;

  return (
    <>
      <ObjectHeader schema={schema} objectId={objectid} />
      <Outlet />
    </>
  );
};

export const Component = ObjectPageLayout;
