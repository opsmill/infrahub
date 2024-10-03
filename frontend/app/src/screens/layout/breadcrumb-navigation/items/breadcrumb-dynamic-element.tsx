import { BreadcrumbItem } from "@/screens/layout/breadcrumb-navigation/type";
import { BreadcrumbLink } from "@/screens/layout/breadcrumb-navigation/items/breadcrumb-link";
import { classNames, warnUnexpectedType } from "@/utils/common";
import { breadcrumbActiveStyle } from "@/screens/layout/breadcrumb-navigation/style";
import BreadcrumbSchemaSelector from "@/screens/layout/breadcrumb-navigation/items/breadcrumb-schema-selector";
import BreadcrumbObjectSelector from "@/screens/layout/breadcrumb-navigation/items/breadcrumb-object-selector";
import BreadcrumbBranchSelector from "@/screens/layout/breadcrumb-navigation/items/breadcrumb-branch-selector";
import React from "react";

export type BreadcrumbDynamicElementProps = BreadcrumbItem & { isLast?: boolean };

export const BreadcrumbDynamicElement = ({ isLast, ...props }: BreadcrumbDynamicElementProps) => {
  if (props.type === "link") {
    return (
      <BreadcrumbLink to={props.to} className={classNames(isLast && breadcrumbActiveStyle)}>
        {props.label}
      </BreadcrumbLink>
    );
  }

  if (props.type === "select") {
    const { value, kind } = props;
    if (kind === "schema") {
      return <BreadcrumbSchemaSelector kind={value} />;
    }

    return <BreadcrumbObjectSelector kind={kind} id={value} />;
  }

  if (props.type === "branch") {
    return <BreadcrumbBranchSelector value={props.value} />;
  }

  warnUnexpectedType(props);
  return null;
};
