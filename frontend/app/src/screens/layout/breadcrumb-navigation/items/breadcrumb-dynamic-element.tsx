import BreadcrumbBranchSelector from "@/screens/layout/breadcrumb-navigation/items/breadcrumb-branch-selector";
import { BreadcrumbLink } from "@/screens/layout/breadcrumb-navigation/items/breadcrumb-link";
import BreadcrumbObjectSelector from "@/screens/layout/breadcrumb-navigation/items/breadcrumb-object-selector";
import BreadcrumbSchemaSelector from "@/screens/layout/breadcrumb-navigation/items/breadcrumb-schema-selector";
import { BreadcrumbItem } from "@/screens/layout/breadcrumb-navigation/type";
import { warnUnexpectedType } from "@/utils/common";

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

  if (props.type === "branch") {
    return <BreadcrumbBranchSelector {...props} />;
  }

  warnUnexpectedType(props);
  return null;
};
