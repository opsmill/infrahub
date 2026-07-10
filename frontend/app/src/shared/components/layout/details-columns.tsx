import type React from "react";

import { Col } from "@/shared/components/container";
import { classNames } from "@/shared/utils/common";

/**
 * Responsive two-column layout for detail screens: stacked on small viewports, a 2/3 main column
 * plus a 1/3 aside from `xl`. The shell is reusable so a page composes its own cards into the
 * columns (see the Profile tab) rather than injecting content into a specific details component.
 */
function DetailsColumns({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={classNames(
        "flex flex-col gap-2 overflow-auto p-2 xl:grid xl:grid-cols-3 xl:items-start",
        className
      )}
    >
      {children}
    </div>
  );
}

function Main({ children, className }: { children: React.ReactNode; className?: string }) {
  return <Col className={classNames("shrink-0 grow md:col-span-2", className)}>{children}</Col>;
}

function Aside({ children, className }: { children: React.ReactNode; className?: string }) {
  return <Col className={className}>{children}</Col>;
}

DetailsColumns.Main = Main;
DetailsColumns.Aside = Aside;

export { DetailsColumns };
