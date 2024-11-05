import { useObjectDetails } from "@/hooks/useObjectDetails";
import { useSchema } from "@/hooks/useSchema";
import { BreadcrumbLink } from "@/screens/layout/breadcrumb-navigation/items/breadcrumb-link";
import BreadcrumbLoading from "@/screens/layout/breadcrumb-navigation/items/breadcrumb-loading";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { getObjectDetailsUrl2 } from "@/utils/objects";
import { NetworkStatus } from "@apollo/client";

export default function BreadcrumbObjectSelector({
  kind,
  id,
  ...props
}: {
  kind: string;
  id: string;
  className?: string;
}) {
  const { schema } = useSchema(kind);

  if (!schema) return <BreadcrumbLoading />;

  return <ObjectSelector schema={schema} id={id} {...props} />;
}

const ObjectSelector = ({
  schema,
  id,
  ...props
}: {
  schema: IModelSchema;
  id: string;
  className?: string;
}) => {
  const { data, error, networkStatus } = useObjectDetails(schema, id);

  if (networkStatus === NetworkStatus.loading) return <BreadcrumbLoading />;

  if (error) return null;

  const objectList = data?.[schema.kind!].edges.map((edge: any) => edge.node);
  if (!objectList || objectList.length === 0) return null;

  const currentObject = objectList.find((node: any) => node.id === id);

  if (!currentObject) return null;

  return (
    <BreadcrumbLink
      to={getObjectDetailsUrl2(currentObject.__typename, currentObject.id)}
      {...props}
    >
      {currentObject.display_label}
    </BreadcrumbLink>
  );
};
