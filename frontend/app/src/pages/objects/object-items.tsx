import ObjectItems from "@/entities/nodes/object-items/object-items-paginated";
import { genericsState, profilesAtom, schemaState } from "@/entities/schema/schema.atom";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { useAtomValue } from "jotai";
import { useParams } from "react-router-dom";

export function ObjectItemsPage() {
  const { objectKind } = useParams();

  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);
  const profiles = useAtomValue(profilesAtom);

  const schema = [...nodes, ...generics, ...profiles].find(({ kind }) => kind === objectKind);

  if (!schema) return <ErrorScreen message={`Object ${objectKind} not found.`} />;

  return <ObjectItems schema={schema} />;
}

export const Component = ObjectItemsPage;
