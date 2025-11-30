import { ChevronsUpDownIcon } from "lucide-react";
import type React from "react";
import { Pressable } from "react-aria-components";

import { Button } from "@/shared/components/buttons/button-primitive";

interface BreadcrumbItemTriggerProps {
  children: React.ReactNode;
}

export function BreadcrumbSelectorTrigger({ children }: BreadcrumbItemTriggerProps) {
  return (
    <Pressable>
      <Button variant="ghost" className="h-auto gap-1.5 rounded-lg px-2 py-1 font-normal">
        <span className="truncate leading-4">{children}</span>
        <ChevronsUpDownIcon className="size-4" />
      </Button>
    </Pressable>
  );
}
