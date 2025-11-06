import { ChevronsUpDownIcon } from "lucide-react";
import type React from "react";
import { Breadcrumb } from "react-aria-components";

import { Button } from "@/shared/components/aria/button";

interface BreadcrumbItemTriggerProps {
  children: React.ReactNode;
}

export function BreadcrumbItemTrigger({ children }: BreadcrumbItemTriggerProps) {
  return (
    <Breadcrumb>
      <Button variant="ghost" className="gap-1.5">
        <span className="truncate">{children}</span>
        <ChevronsUpDownIcon className="size-4" />
      </Button>
    </Breadcrumb>
  );
}
