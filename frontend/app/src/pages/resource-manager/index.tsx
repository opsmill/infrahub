import ObjectHeader from "@/entities/nodes/object-header";
import { ObjectsTableManager } from "@/entities/nodes/object/ui/objects-table/objects-table-manager";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/constants";
import { genericsState } from "@/entities/schema/stores/schema.atom";
import Content from "@/shared/components/layout/content";
import { LoadingScreen } from "@/shared/components/loading/loading-screen";
import { useAtomValue } from "jotai/index";

const ResourceManagerPage = () => {
  const generics = useAtomValue(genericsState);
  const resourcePoolSchema = generics.find(({ kind }) => kind === RESOURCE_GENERIC_KIND);

  if (!resourcePoolSchema) return <LoadingScreen className="h-full" />;

  return (
    <Content.Card>
      <ObjectHeader schema={resourcePoolSchema} />

      <ObjectsTableManager schema={resourcePoolSchema} />
    </Content.Card>
  );
};

export const Component = ResourceManagerPage;
