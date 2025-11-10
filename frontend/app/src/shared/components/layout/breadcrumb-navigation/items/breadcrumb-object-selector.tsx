import { BreadcrumbLink } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-link";
import BreadcrumbLoading from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-loading";

import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

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
  schema: ModelSchema;
  id: string;
  className?: string;
}) => {
  const { data, error, isPending } = useGetObject({ objectSchema: schema, objectId: id });

  if (isPending) return <BreadcrumbLoading />;

  if (error) return null;

  return (
    <BreadcrumbLink to={getObjectDetailsUrl(data.__typename, data.id)} {...props}>
      {getNodeLabel(data)}
    </BreadcrumbLink>
  );
};
