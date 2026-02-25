import { Command } from "cmdk";
import { useEffect, useState } from "react";

import { SearchAnywhereDialog } from "@/entities/navigation/ui/search-anywhere/search-anywhere-dialog";
import { SearchAnywhereEmpty } from "@/entities/navigation/ui/search-anywhere/search-anywhere-empty";
import { SearchAnywhereInput } from "@/entities/navigation/ui/search-anywhere/search-anywhere-input";
import { SearchAnywhereTrigger } from "@/entities/navigation/ui/search-anywhere/search-anywhere-trigger";

import { SearchActions } from "./search-actions";
import { SearchAnywhereContext } from "./search-anywhere-context";
import { SearchAnywhereFooter } from "./search-anywhere-footer";
import { SearchDocs } from "./search-docs";
import { SearchNodes } from "./search-nodes";
import { SearchParentPrefixes } from "./search-parent-prefixes";

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

          <Command.List className="max-h-[60vh] overflow-y-auto [&_[cmdk-group]]:mt-2">
            <SearchAnywhereEmpty />
            <SearchActions />
            <SearchParentPrefixes />
            <SearchNodes />
            <SearchDocs />
          </Command.List>

          <SearchAnywhereFooter />
        </Command>
      </SearchAnywhereDialog>
    </SearchAnywhereContext>
  );
}
