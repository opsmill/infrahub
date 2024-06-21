import LoadingScreen from "@/screens/loading-screen/loading-screen";
import ObjectItems from "@/screens/object-items/object-items-paginated";
import { genericsState } from "@/state/atoms/schema.atom";
import { constructPath } from "@/utils/fetch";
import { useAtomValue } from "jotai/index";
import { RESOURCE_GENERIC_KIND } from "./constants";

const ResourceManagerPage = () => {
  const generics = useAtomValue(genericsState);
  const resourcePoolSchema = generics.find(({ kind }) => kind === RESOURCE_GENERIC_KIND);

  if (!resourcePoolSchema) return <LoadingScreen />;

  return (
    <ObjectItems
      objectname={resourcePoolSchema.kind || RESOURCE_GENERIC_KIND}
      overrideDetailsViewUrl={(objectId) => constructPath(`/resource-manager/${objectId}`)}
    />
  );
};

export function Component() {
  return <ResourceManagerPage />;
}
