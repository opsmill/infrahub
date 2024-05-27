import { useAtomValue } from "jotai/index";
import { genericsState } from "../../state/atoms/schema.atom";
import { RESOURCE_GENERIC_KIND } from "./constants";
import LoadingScreen from "../loading-screen/loading-screen";
import ObjectItems from "../object-items/object-items-paginated";
import { constructPath } from "../../utils/fetch";

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

export default ResourceManagerPage;
