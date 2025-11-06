import { ChevronsUpDownIcon } from "lucide-react";
import type React from "react";

import { Button } from "@/shared/components/aria/button";
import { BreadcrumbSeparator } from "@/shared/components/ui/breadcrumb";

interface BreadcrumbItemTriggerProps {
  children: React.ReactNode;
}

export function BreadcrumbItemTrigger({ children }: BreadcrumbItemTriggerProps) {
  return (
    <>
      <BreadcrumbSeparator />
      <Button variant="ghost" className="gap-1.5">
        <span className="truncate">{children}</span>
        <ChevronsUpDownIcon className="size-4" />
      </Button>
    </>
  );
}
