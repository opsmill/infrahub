import { PROFILE_KIND } from "@/config/constants";
import { getObjectDetailsUrl2 } from "@/entities/nodes/objects";
import { useSchema } from "@/entities/schema/useSchema";
import { BreadcrumbLink } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-link";
import BreadcrumbLoading from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-loading";
import { breadcrumbActiveStyle } from "@/shared/components/layout/breadcrumb-navigation/style";
import { BreadcrumbSeparator } from "@/shared/components/ui/breadcrumb";
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
