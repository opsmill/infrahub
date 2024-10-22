import { Button, ButtonProps } from "@/components/buttons/button-primitive";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import Kbd from "@/components/ui/kbd";
import { CollapsedButton } from "@/screens/layout/menu-navigation/components/collapsed-button";
import { classNames } from "@/utils/common";
import { Combobox, Dialog, Transition } from "@headlessui/react";
import { Icon } from "@iconify-icon/react";
import { Fragment, ReactNode, forwardRef, useEffect, useState } from "react";
import { Link, LinkProps, useNavigate } from "react-router-dom";
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
      <div className="flex items-center gap-2">
        <Icon icon="mdi:magnify" aria-hidden="true" className="text-xl" />
        <span className="text-neutral-700 text-sm group-data-[collapsed=true]/sidebar:hidden transition-all">
          Search
        </span>
      </div>

      <Kbd keys="command" className="group-data-[collapsed=true]/sidebar:hidden transition-all">
        K
      </Kbd>
    </Button>
  );
};

type SearchModalProps = {
  className?: string;
  isCollapsed?: boolean;
};
export function SearchAnywhere({ className = "", isCollapsed }: SearchModalProps) {
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
          className={className}
        />
      ) : (
        <SearchAnywhereTriggerButton
          onClick={openModal}
          onChange={openModal}
          className={className}
        />
      )}

      <Transition appear show={isOpen} as={Fragment}>
        <Dialog onClose={closeDrawer}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-300"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-200"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-gray-600/25" />
          </Transition.Child>

          <div className="fixed inset-0">
            <div className="flex items-center justify-center p-4 pt-1">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-300"
                enterFrom="opacity-0 scale-95"
                enterTo="opacity-100 scale-100"
                leave="ease-in duration-200"
                leaveFrom="opacity-100 scale-100"
                leaveTo="opacity-0 scale-95"
              >
                <SearchAnywhereDialog onSelection={closeDrawer} />
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>
    </>
  );
}

type SearchAnywhereProps = {
  onSelection: (url?: string) => void;
};

const SearchAnywhereDialog = forwardRef<HTMLDivElement, SearchAnywhereProps>(
  ({ onSelection }, forwardedRef) => {
    const navigate = useNavigate();
    const [query, setQuery] = useState("");

    return (
      <Dialog.Panel
        ref={forwardedRef}
        className="p-2 w-full max-w-screen-md rounded-xl bg-stone-100 shadow-xl transition-all space-y-2"
        data-testid="search-anywhere"
      >
        <Combobox
          onChange={(url: string) => {
            if (url.length === 0) return;

            if (url.startsWith("http")) {
              window.open(url, "_blank", "rel=noopener noreferrer, popup=false");
            } else {
              navigate(url);
            }

            onSelection(url);
          }}
        >
          <div className="relative">
            <Combobox.Button className="absolute top-2.5 pl-2.5">
              <Icon icon="mdi:magnify" className="text-xl text-custom-blue-600" />
            </Combobox.Button>

            <Combobox.Input
              as={Input}
              placeholder="Search anywhere"
              onChange={(e) => setQuery(e.target.value)}
              value={query}
              className="w-full px-9 py-2"
            />
          </div>

          {query && (
            <Combobox.Options static className="overflow-x-hidden overflow-y-auto space-y-2">
              <SearchActions query={query} />
              <SearchNodes query={query} />
              <SearchDocs query={query} />
            </Combobox.Options>
          )}
        </Combobox>
      </Dialog.Panel>
    );
  }
);

type SearchGroupProps = {
  children: ReactNode;
};

export const SearchGroup = ({ children }: SearchGroupProps) => {
  return <Card className="p-2">{children}</Card>;
};

export const SearchGroupTitle = ({ children }: SearchGroupProps) => {
  return (
    <Combobox.Option
      value=""
      disabled
      className="text-xs mb-0.5 pl-1.5 font-semibold text-neutral-600 flex items-center"
    >
      {children}
    </Combobox.Option>
  );
};

export const SearchResultItem = ({ className = "", children, to, ...props }: LinkProps) => {
  return (
    <Combobox.Option
      as={Link}
      value={to}
      to={to}
      {...props}
      className={({ active }) =>
        classNames(
          `flex items-center gap-1 text-xs p-2 rounded ${active ? "bg-gray-100" : ""}`,
          className
        )
      }
    >
      {children}
    </Combobox.Option>
  );
};
