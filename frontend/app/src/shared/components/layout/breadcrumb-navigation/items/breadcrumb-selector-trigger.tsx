import { ChevronsUpDownIcon } from "lucide-react";
import type React from "react";

import { Button } from "@/shared/components/aria/button";

interface BreadcrumbItemTriggerProps {
  children: React.ReactNode;
}

export function BreadcrumbSelectorTrigger({ children }: BreadcrumbItemTriggerProps) {
  return (
    <Button variant="ghost" className="gap-1.5">
      <span className="truncate">{children}</span>
      <ChevronsUpDownIcon className="size-4" />
    </Button>
  );
}
