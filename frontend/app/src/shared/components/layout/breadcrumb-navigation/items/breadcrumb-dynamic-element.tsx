import { BreadcrumbLink } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-link";
import BreadcrumbObjectSelector from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-object-selector";
import BreadcrumbSchemaSelector from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-schema-selector";
import type { BreadcrumbItem } from "@/shared/components/layout/breadcrumb-navigation/type";
import { warnUnexpectedType } from "@/shared/utils/common";

import BreadcrumbObjectIdDisplay from "./breadcrumb-object-id";

export type BreadcrumbDynamicElementProps = BreadcrumbItem & {
  isLast?: boolean;
  className?: string;
};

export const BreadcrumbDynamicElement = ({ ...props }: BreadcrumbDynamicElementProps) => {
  if (props.type === "link") {
    return <BreadcrumbLink {...props}>{props.label}</BreadcrumbLink>;
  }

  if (props.type === "select") {
    const { value, kind, ...otherProps } = props;
    if (kind === "schema") {
      return <BreadcrumbSchemaSelector kind={value} {...otherProps} />;
    }

    return <BreadcrumbObjectSelector kind={kind} id={value} {...otherProps} />;
  }

  if (props.type === "id") {
    const { value, ...otherProps } = props;

    return <BreadcrumbObjectIdDisplay id={value} {...otherProps} />;
  }

  warnUnexpectedType(props);
  return null;
};
