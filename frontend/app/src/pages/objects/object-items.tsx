import { useAtomValue } from "jotai";
import { useParams } from "react-router-dom";

import ErrorScreen from "@/screens/errors/error-screen";
import ObjectItems from "@/screens/object-items/object-items-paginated";
import { genericsState, profilesAtom, schemaState } from "@/state/atoms/schema.atom";
import Content from "@/screens/layout/content";
import useFilters from "@/hooks/useFilters";

export function ObjectItemsPage() {
  const { objectKind } = useParams();
  const [filters] = useFilters();

  const kindFilter = filters?.find((filter) => filter.name == "kind__value");

  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);
  const profiles = useAtomValue(profilesAtom);

  const requestedKind = kindFilter?.value ?? objectKind;

  const schema = [...nodes, ...generics, ...profiles].find(({ kind }) => kind === requestedKind);

  if (!schema) return <ErrorScreen message={`Object ${objectKind} not found.`} />;

  return (
    <Content>
      <ObjectItems schema={schema} />
    </Content>
  );
}

export const Component = ObjectItemsPage;
