import Content from "@/screens/layout/content";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import ObjectItems from "@/screens/object-items/object-items-paginated";
import ObjectHeader from "@/screens/objects/object-header";
import { RESOURCE_GENERIC_KIND } from "@/screens/resource-manager/constants";
import { genericsState } from "@/state/atoms/schema.atom";
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
