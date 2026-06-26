import { Button } from "@infrahub/ui";
import { ChevronsUpDownIcon } from "lucide-react";
import type React from "react";

interface BreadcrumbItemTriggerProps {
  children: React.ReactNode;
}

export function BreadcrumbSelectorTrigger({ children }: BreadcrumbItemTriggerProps) {
  return (
    <Button variant="ghost" className="h-auto gap-1.5 rounded-lg px-2 py-1 font-normal">
      <span className="truncate leading-4">{children}</span>
      <ChevronsUpDownIcon className="size-4" />
    </Button>
  );
}
