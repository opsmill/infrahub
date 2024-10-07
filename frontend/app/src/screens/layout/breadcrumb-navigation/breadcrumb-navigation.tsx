import { Breadcrumb, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import React from "react";
import { UIMatch, useMatches } from "react-router-dom";
import {
  BreadcrumbDynamicElement,
  BreadcrumbDynamicElementProps,
} from "@/screens/layout/breadcrumb-navigation/items/breadcrumb-dynamic-element";
import { classNames } from "@/utils/common";
import { breadcrumbActiveStyle } from "@/screens/layout/breadcrumb-navigation/style";

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
          <BreadcrumbDynamicElement
            {...crumb}
            className={classNames(index === crumbs.length - 1 && breadcrumbActiveStyle)}
          />
        </React.Fragment>
      ))}
    </Breadcrumb>
  );
}
