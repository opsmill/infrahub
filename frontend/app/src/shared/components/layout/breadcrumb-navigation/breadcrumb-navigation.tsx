import React from "react";
import { matchPath, type UIMatch, useLocation, useMatches, useParams } from "react-router";

import { BreadcrumbBranches } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-branches";
import { BreadcrumbObjects } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-objects";
import {
  BreadcrumbDynamicElement,
  type BreadcrumbDynamicElementProps,
} from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-dynamic-element";
import { breadcrumbActiveStyle } from "@/shared/components/layout/breadcrumb-navigation/style";
import { Breadcrumb, BreadcrumbSeparator } from "@/shared/components/ui/breadcrumb";
import { classNames } from "@/shared/utils/common";

export default function BreadcrumbNavigation() {
  const { pathname } = useLocation();
  const { objectKind } = useParams();
  const matches = useMatches() as UIMatch<
    unknown,
    { breadcrumb?: (match: UIMatch) => BreadcrumbDynamicElementProps }
  >[];

  if (matchPath({ path: "/branches", end: false }, pathname)) {
    return <BreadcrumbBranches />;
  }

  if (objectKind) {
    return <BreadcrumbObjects />;
  }

  const crumbs = matches
    .map((match) => match.handle?.breadcrumb?.(match))
    .filter((match) => !!match);

  return (
    <Breadcrumb>
      {crumbs.map((crumb, index) => (
        <React.Fragment key={index}>
          <BreadcrumbSeparator />
          <BreadcrumbDynamicElement
            {...crumb}
            className={classNames(index === crumbs.length - 1 && breadcrumbActiveStyle)}
          />
        </React.Fragment>
      ))}
    </Breadcrumb>
  );
}
