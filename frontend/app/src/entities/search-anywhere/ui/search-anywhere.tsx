import { Command } from "cmdk";
import { useEffect, useState } from "react";

import { SearchAnywhereDialog } from "@/entities/search-anywhere/ui/search-anywhere-dialog";
import { SearchAnywhereEmpty } from "@/entities/search-anywhere/ui/search-anywhere-empty";
import { SearchAnywhereInput } from "@/entities/search-anywhere/ui/search-anywhere-input";
import { SearchAnywhereTrigger } from "@/entities/search-anywhere/ui/search-anywhere-trigger";

import { SearchActions } from "./search-actions";
import { SearchAnywhereContext } from "./search-anywhere-context";
import { SearchDocs } from "./search-docs";
import { SearchNodes } from "./search-nodes";

type SearchModalProps = {
  isCollapsed?: boolean;
};

export function SearchAnywhere({ isCollapsed }: SearchModalProps) {
  let [isOpen, setIsOpen] = useState(false);

  function closeDialog() {
    setIsOpen(false);
  }

  function openDialog() {
    setIsOpen(true);
  }

  useEffect(() => {
    const onSearchAnywhereShortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setIsOpen((prev) => !prev);
      }
    };

    document.addEventListener("keydown", onSearchAnywhereShortcut);
    return () => document.removeEventListener("keydown", onSearchAnywhereShortcut);
  }, []);

  return (
    <SearchAnywhereContext
      value={{
        isOpen,
        setIsOpen,
        closeDialog,
        openDialog,
      }}
    >
      <SearchAnywhereTrigger isCollapsed={isCollapsed} onClick={openDialog} />

      <SearchAnywhereDialog>
        <Command shouldFilter={false}>
          <SearchAnywhereInput />

          <Command.List className="[&_[cmdk-group]]:mt-2">
            <SearchAnywhereEmpty />
            <SearchActions />
            <SearchNodes />
            <SearchDocs />
          </Command.List>
        </Command>
      </SearchAnywhereDialog>
    </SearchAnywhereContext>
  );
}
