import { useAtomValue } from "jotai/index";

import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { ObjectsManager } from "@/entities/nodes/object/ui/objects-manager";
import ObjectHeader from "@/entities/nodes/object-header";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/constants";
import { genericSchemasAtom } from "@/entities/schema/stores/schema.atom";

const ResourceManagerPage = () => {
  const generics = useAtomValue(genericSchemasAtom);
  const resourcePoolSchema = generics.find(({ kind }) => kind === RESOURCE_GENERIC_KIND);

  if (!resourcePoolSchema) return <LoadingIndicator className="h-full" />;

  return (
    <Content.Card className="flex flex-col">
      <ObjectHeader schema={resourcePoolSchema} />

      <ObjectsManager schema={resourcePoolSchema} />
    </Content.Card>
  );
};

export const Component = ResourceManagerPage;
