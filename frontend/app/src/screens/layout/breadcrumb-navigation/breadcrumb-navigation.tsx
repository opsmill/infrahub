import { Breadcrumb, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import React from "react";
import { UIMatch, useMatches } from "react-router-dom";
import {
  BreadcrumbDynamicElement,
  BreadcrumbDynamicElementProps,
} from "@/screens/layout/breadcrumb-navigation/items/breadcrumb-dynamic-element";

export default function BreadcrumbNavigation() {
  const matches = useMatches() as UIMatch<
    unknown,
    { breadcrumb?: (match: UIMatch) => BreadcrumbDynamicElementProps }
  >[];

  const crumbs = matches
    .map((match) => match.handle?.breadcrumb?.(match))
    .filter((match) => !!match);

  return (
    <Breadcrumb>
      {crumbs.map((crumb, index) => (
        <React.Fragment key={index}>
          <BreadcrumbSeparator />
          <BreadcrumbDynamicElement {...crumb} isLast={index === crumbs.length - 1} />
        </React.Fragment>
      ))}
    </Breadcrumb>
  );
}
