import type React from "react";

import { Col } from "@/shared/components/container";
import { classNames } from "@/shared/utils/common";

// Responsive detail-screen layout: stacked on small viewports, 2/3 main + 1/3 aside from xl; pages compose their own cards.
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
