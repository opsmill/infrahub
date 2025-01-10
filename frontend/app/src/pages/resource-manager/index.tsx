import ObjectHeader from "@/entities/nodes/object-header";
import ObjectItems from "@/entities/nodes/object-items/object-items-paginated";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/constants";
import { genericsState } from "@/entities/schema/schema.atom";
import Content from "@/shared/components/layout/content";
import LoadingScreen from "@/shared/components/loading-screen";
import { useAtomValue } from "jotai/index";

const ResourceManagerPage = () => {
  const generics = useAtomValue(genericsState);
  const resourcePoolSchema = generics.find(({ kind }) => kind === RESOURCE_GENERIC_KIND);

  if (!resourcePoolSchema) return <LoadingScreen />;

  return (
    <Content.Card>
      <ObjectHeader schema={resourcePoolSchema} />

      <ObjectItems schema={resourcePoolSchema} />
    </Content.Card>
  );
};

export const Component = ResourceManagerPage;
