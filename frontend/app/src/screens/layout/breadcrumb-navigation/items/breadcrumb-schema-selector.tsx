import { BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import { PROFILE_KIND } from "@/config/constants";
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
  const { schema, isProfile, isNode } = useSchema(kind);

  if (!schema) {
    return <BreadcrumbLoading />;
  }

  if (isProfile) {
    return (
      <>
        <BreadcrumbSchemaSelector kind={PROFILE_KIND} />
        <BreadcrumbSeparator />
        <BreadcrumbLink
          to={getObjectDetailsUrl2(kind)}
          className={classNames(isLast && breadcrumbActiveStyle)}
          {...props}
        >
          {schema.label}
        </BreadcrumbLink>
      </>
    );
  }

  if (isNode && schema.hierarchy) {
    return (
      <>
        <BreadcrumbSchemaSelector kind={schema.hierarchy} />
        <BreadcrumbSeparator />
        <BreadcrumbLink
          to={getObjectDetailsUrl2(kind)}
          className={classNames(isLast && breadcrumbActiveStyle)}
          {...props}
        >
          {schema.label}
        </BreadcrumbLink>
      </>
    );
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
