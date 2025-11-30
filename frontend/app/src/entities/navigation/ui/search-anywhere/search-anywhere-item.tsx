import type React from "react";
import { useNavigate } from "react-router";

import { CommandItem } from "@/shared/components/ui/command";

import { useSearchAnywhereContext } from "@/entities/navigation/ui/search-anywhere/search-anywhere-context";

export interface SearchAnywhereItemProps extends React.ComponentProps<typeof CommandItem> {
  to: string;
}

export function SearchAnywhereItem({ to, ...props }: SearchAnywhereItemProps) {
  const { closeDialog } = useSearchAnywhereContext();
  const navigate = useNavigate();

  return (
    <CommandItem
      {...props}
      onSelect={() => {
        if (to.startsWith("http")) {
          window.open(to, "_blank", "rel=noopener noreferrer, popup=false");
        } else {
          navigate(to);
        }

        closeDialog();
      }}
    />
  );
}
