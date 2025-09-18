import React from "react";
import { type UIMatch, useMatches } from "react-router";

import {
  BreadcrumbDynamicElement,
  type BreadcrumbDynamicElementProps,
} from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-dynamic-element";
import { breadcrumbActiveStyle } from "@/shared/components/layout/breadcrumb-navigation/style";
import { Breadcrumb, BreadcrumbSeparator } from "@/shared/components/ui/breadcrumb";
import { classNames } from "@/shared/utils/common";

export default function BreadcrumbNavigation() {
  const matches = useMatches() as UIMatch<
    unknown,
    { breadcrumb?: (match: UIMatch) => BreadcrumbDynamicElementProps }
  >[];

  const crumbs = matches
    .map((match) => match.handle?.breadcrumb?.(match))
    .filter((match) => !!match);

  return (
    <Breadcrumb data-testid="breadcrumb-navigation">
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
