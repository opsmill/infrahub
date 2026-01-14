import { useAtomValue } from "jotai";

import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";

import { ObjectItemsHeader } from "@/entities/nodes/object/ui/object-items-header";
import { ObjectsManager } from "@/entities/nodes/object/ui/objects-manager";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/constants";
import { genericSchemasAtom } from "@/entities/schema/stores/schema.atom";

const ResourceManagerPage = () => {
  const generics = useAtomValue(genericSchemasAtom);
  const resourcePoolSchema = generics.find(({ kind }) => kind === RESOURCE_GENERIC_KIND);

  if (!resourcePoolSchema) {
    return <ErrorScreen message={`Schema ${RESOURCE_GENERIC_KIND} not found.`} />;
  }

  return (
    <Content.Card className="flex flex-col">
      <ObjectItemsHeader schema={resourcePoolSchema} />

      <ObjectsManager schema={resourcePoolSchema} />
    </Content.Card>
  );
};

export const Component = ResourceManagerPage;
