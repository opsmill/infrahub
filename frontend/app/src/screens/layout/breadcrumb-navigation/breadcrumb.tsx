import { Breadcrumb, BreadcrumbSeparator } from "@/components/breadcrumb/breadcrumb";
import React from "react";
import { UIMatch, useMatches } from "react-router-dom";

import BreadcrumbSchemaSelector from "@/screens/layout/breadcrumb-navigation/breadcrumb-schema-selector";
import { classNames, warnUnexpectedType } from "@/utils/common";
import { BreadcrumbLink } from "@/screens/layout/breadcrumb-navigation/breadcrumb-link";
import BreadcrumbBranchSelector from "@/screens/layout/breadcrumb-navigation/breadcrumb-branch-selector";
import BreadcrumbObjectSelector from "@/screens/layout/breadcrumb-navigation/breadcrumb-object-selector";

type BreadcrumbNavigationItemProps = (
  | { type: "select"; value: string; kind: string }
  | { type: "link"; label: string; to: string }
  | { type: "branch"; value: string }
) & { isLast?: boolean };

export default function BreadcrumbNavigation() {
  const matches = useMatches() as UIMatch<
    unknown,
    { breadcrumb?: (match: UIMatch) => BreadcrumbNavigationItemProps }
  >[];

  const crumbs = matches
    .map((match) => match.handle?.breadcrumb?.(match))
    .filter((match) => !!match);

  return (
    <Breadcrumb>
      {crumbs.map((crumb, index) => (
        <React.Fragment key={index}>
          <BreadcrumbSeparator />
          <BreadcrumbElement {...crumb} isLast={index === crumbs.length - 1} />
        </React.Fragment>
      ))}
    </Breadcrumb>
  );
}

const BreadcrumbElement = ({ isLast, ...props }: BreadcrumbNavigationItemProps) => {
  if (props.type === "link") {
    return (
      <BreadcrumbLink
        to={props.to}
        className={classNames(isLast && "bg-indigo-50 text-indigo-700 hover:bg-indigo-100")}>
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
