import { Button, ButtonProps } from "@/components/buttons/button-primitive";
import Kbd from "@/components/ui/kbd";
import { CollapsedButton } from "@/screens/layout/menu-navigation/components/collapsed-button";
import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import { Command } from "cmdk";
import React, { ReactNode, useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Input } from "../ui/input";
import { SearchActions } from "./search-actions";
import { SearchDocs } from "./search-docs";
import { SearchNodes } from "./search-nodes";

const SearchAnywhereTriggerButton = ({ className, ...props }: ButtonProps) => {
  return (
    <Button
      variant="ghost"
      className={classNames(
        "px-3 py-2 gap-3 bg-neutral-100 shadow-none text-neutral-800 justify-between",
        className
      )}
      data-testid="search-anywhere-trigger"
      {...props}
    >
      <div className="flex items-center gap-2 overflow-hidden">
        <Icon icon="mdi:magnify" aria-hidden="true" className="text-xl" />
        <span className="text-neutral-700 text-sm group-data-[collapsed=true]/sidebar:hidden transition-all truncate">
          Search
        </span>
      </div>

      <Kbd keys="command" className="group-data-[collapsed=true]/sidebar:hidden transition-all">
        K
      </Kbd>
    </Button>
  );
};

interface SearchAnywhereContextProps {
  closeDrawer?: () => void;
}

export const SearchAnywhereContext = React.createContext<SearchAnywhereContextProps>({});

type SearchModalProps = {
  isCollapsed?: boolean;
};

export function SearchAnywhere({ isCollapsed }: SearchModalProps) {
  let [isOpen, setIsOpen] = useState(false);

  function closeDrawer() {
    setIsOpen(false);
  }

  function openModal() {
    setIsOpen(true);
  }

  useEffect(() => {
    const onSearchAnywhereShortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        openModal();
      }
    };

    document.addEventListener("keydown", onSearchAnywhereShortcut);
    return () => document.removeEventListener("keydown", onSearchAnywhereShortcut);
  }, []);

  return (
    <>
      {isCollapsed ? (
        <CollapsedButton
          tooltipContent="Search anywhere"
          icon="mdi:search"
          onClick={openModal}
          onChange={openModal}
        />
      ) : (
        <SearchAnywhereTriggerButton onClick={openModal} />
      )}

      <Command.Dialog
        open={isOpen}
        onOpenChange={closeDrawer}
        data-testid="search-anywhere"
        shouldFilter={false}
        className="fixed inset-0"
      >
        <div
          className="fixed inset-0 flex flex-col items-center bg-gray-600/25 animate-in fade-in"
          onClick={closeDrawer}
        >
          <SearchAnywhereContext.Provider value={{ closeDrawer }}>
            <SearchAnywhereDialog className="mt-1 animate-in fade-in" />
          </SearchAnywhereContext.Provider>
        </div>
      </Command.Dialog>
    </>
  );
}

type SearchAnywhereProps = {
  className?: string;
};

const SearchAnywhereDialog = ({ className }: SearchAnywhereProps) => {
  const [query, setQuery] = useState("");

  return (
    <div
      className={classNames(
        "p-2 w-full max-w-screen-md rounded-xl bg-stone-100 shadow-xl",
        className
      )}
      onClick={(event) => event.stopPropagation()}
    >
      <div className="relative">
        <div className="absolute top-2.5 pl-2.5">
          <Icon icon="mdi:magnify" className="text-xl text-custom-blue-600" />
        </div>

        <Input
          placeholder="Search anywhere"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
          }}
          className="px-9 py-2"
        />
      </div>

      {query && (
        <Command.List className="pt-2">
          <div className="overflow-x-hidden overflow-y-auto space-y-2">
            <SearchActions query={query} />

            <SearchNodes query={query} />

            <SearchDocs query={query} />
          </div>
        </Command.List>
      )}
    </div>
  );
};

type SearchGroupProps = {
  children: ReactNode;
};

export const SearchGroup = ({ children }: SearchGroupProps) => {
  return (
    <Command.Group className="bg-custom-white rounded-lg border p-2">{children}</Command.Group>
  );
};

export const SearchGroupTitle = ({ children }: SearchGroupProps) => {
  return (
    <div className="text-xs mb-0.5 pl-1.5 font-semibold text-neutral-600 flex items-center">
      {children}
    </div>
  );
};

type SearchResultItemProps = {
  children: ReactNode;
  className?: string;
  to: string;
};

export const SearchResultItem = ({
  className = "",
  children,
  to,
  ...props
}: SearchResultItemProps) => {
  const navigate = useNavigate();
  const { closeDrawer } = useContext(SearchAnywhereContext);

  return (
    <Command.Item
      {...props}
      onSelect={() => {
        if (to.length === 0) return;

        if (to.startsWith("http")) {
          window.open(to, "_blank", "rel=noopener noreferrer, popup=false");
        } else {
          navigate(to);
        }

        if (closeDrawer) {
          closeDrawer();
        }
      }}
    >
      <Button
        variant={"ghost"}
        className={classNames(
          "flex justify-start w-full h-min gap-1 text-xs p-2 m-0 rounded text-wrap text-left hover:bg-gray-100",
          className
        )}
      >
        {children}
      </Button>
    </Command.Item>
  );
};
