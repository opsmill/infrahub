import { useSchema } from "@/hooks/useSchema";
import { BreadcrumbLink } from "@/screens/layout/breadcrumb-navigation/items/breadcrumb-link";
import BreadcrumbLoading from "@/screens/layout/breadcrumb-navigation/items/breadcrumb-loading";
import { breadcrumbActiveStyle } from "@/screens/layout/breadcrumb-navigation/style";
import { classNames } from "@/utils/common";
import { getObjectDetailsUrl2 } from "@/utils/objects";

interface BreadcrumbSchemaSelectorProps {
  kind: string;
  isLast?: boolean;
  className?: string;
}
export default function BreadcrumbSchemaSelector({
  isLast,
  kind,
  ...props
}: BreadcrumbSchemaSelectorProps) {
  const { schema } = useSchema(kind);

  if (!schema) {
    return <BreadcrumbLoading />;
  }

  return (
    <BreadcrumbLink
      to={getObjectDetailsUrl2(kind)}
      className={classNames(isLast && breadcrumbActiveStyle)}
      {...props}
    >
      {schema.label}
    </BreadcrumbLink>
  );
}
