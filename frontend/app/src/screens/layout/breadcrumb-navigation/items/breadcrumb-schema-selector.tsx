import { PROFILE_KIND } from "@/config/constants";
import { BreadcrumbLink } from "@/screens/layout/breadcrumb-navigation/items/breadcrumb-link";
import BreadcrumbLoading from "@/screens/layout/breadcrumb-navigation/items/breadcrumb-loading";
import { breadcrumbActiveStyle } from "@/screens/layout/breadcrumb-navigation/style";
import { getObjectDetailsUrl2 } from "@/screens/objects/objects";
import { BreadcrumbSeparator } from "@/shared/components/ui/breadcrumb";
import { useSchema } from "@/shared/hooks/useSchema";
import { classNames } from "@/shared/utils/common";

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
