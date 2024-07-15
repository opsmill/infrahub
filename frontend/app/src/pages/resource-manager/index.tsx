import { useAtomValue } from "jotai/index";
import { genericsState } from "@/state/atoms/schema.atom";
import { RESOURCE_GENERIC_KIND } from "@/screens/resource-manager/constants";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import ObjectItems from "@/screens/object-items/object-items-paginated";
import { constructPath } from "@/utils/fetch";
import ObjectHeader from "@/screens/objects/object-header";
import Content from "@/screens/layout/content";

const ResourceManagerPage = () => {
  const generics = useAtomValue(genericsState);
  const resourcePoolSchema = generics.find(({ kind }) => kind === RESOURCE_GENERIC_KIND);

  if (!resourcePoolSchema) return <LoadingScreen />;

  return (
    <>
      <ObjectHeader schema={resourcePoolSchema} />

      <Content className="p-2">
        <ObjectItems
          schema={resourcePoolSchema}
          overrideDetailsViewUrl={(objectId) => constructPath(`/resource-manager/${objectId}`)}
        />
      </Content>
    </>
  );
};

export const Component = ResourceManagerPage;
