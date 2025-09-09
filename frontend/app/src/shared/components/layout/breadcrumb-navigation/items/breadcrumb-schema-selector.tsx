import { PROFILE_KIND } from "@/config/constants";

import { BreadcrumbLink } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-link";
import BreadcrumbLoading from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-loading";
import { breadcrumbActiveStyle } from "@/shared/components/layout/breadcrumb-navigation/style";
import { BreadcrumbSeparator } from "@/shared/components/ui/breadcrumb";
import { classNames } from "@/shared/utils/common";

import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

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
          to={getObjectDetailsUrl(kind)}
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
          to={getObjectDetailsUrl(kind)}
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
      to={getObjectDetailsUrl(kind)}
      className={classNames(isLast && breadcrumbActiveStyle)}
      {...props}
    >
      {schema.label}
    </BreadcrumbLink>
  );
}
