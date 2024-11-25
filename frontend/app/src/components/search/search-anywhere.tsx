import { Button, ButtonProps } from "@/components/buttons/button-primitive";
import { Card } from "@/components/ui/card";
import Kbd from "@/components/ui/kbd";
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

export function SearchAnywhere() {
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
      <SearchAnywhereTriggerButton onClick={openModal} />

      <Command.Dialog
        open={isOpen}
        onOpenChange={closeDrawer}
        data-testid="search-anywhere"
        shouldFilter={false}
        className="fixed w-full h-full top-0 left-0"
      >
        <div className="fixed inset-0 bg-gray-600/25 animate-in fade-in" onClick={closeDrawer} />

        <SearchAnywhereContext.Provider value={{ closeDrawer }}>
          <SearchAnywhereDialog className="fixed mt-1 left-1/2 -translate-x-1/2 animate-in fade-in" />
        </SearchAnywhereContext.Provider>
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
        "p-2 w-full max-w-screen-md rounded-xl bg-stone-100 shadow-xl space-y-2",
        className
      )}
    >
      <div className="relative bg-white">
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
        <Command.List>
          <div className="overflow-x-hidden overflow-y-auto space-y-2">
            <Command.Group>
              <SearchActions query={query} />
            </Command.Group>

            <Command.Group>
              <SearchNodes query={query} />
            </Command.Group>

            <Command.Group>
              <SearchDocs query={query} />
            </Command.Group>
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
  return <Card className="p-2">{children}</Card>;
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
          "flex justify-start w-full gap-1 text-xs p-2 m-0 rounded text-wrap text-left hover:bg-gray-100",
          className
        )}
      >
        {children}
      </Button>
    </Command.Item>
  );
};
