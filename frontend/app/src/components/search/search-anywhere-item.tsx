import { useSearchAnywhereContext } from "@/components/search/search-anywhere-context";
import { CommandItem } from "@/components/ui/command";
import React from "react";
import { useNavigate } from "react-router-dom";

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
