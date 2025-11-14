import { SearchIcon, XIcon } from "lucide-react";
import {
  Autocomplete as AriaAutocomplete,
  type AutocompleteProps as AriaAutocompleteProps,
  Button as AriaButton,
  Input as AriaInput,
  type InputProps as AriaInputProps,
  SearchField as AriaSearchField,
  type SearchFieldProps as AriaSearchFieldProps,
} from "react-aria-components";

import { classNames } from "@/shared/utils/common";

export function Autocomplete({ children, ...props }: AriaAutocompleteProps) {
  return (
    <AriaAutocomplete {...props}>
      <div className="max-h-[inherit] overflow-hidden">
        <AutocompleteSearchField placeholder="Search..." />
        {children}
      </div>
    </AriaAutocomplete>
  );
}

export interface SearchInputProps extends AriaSearchFieldProps {
  placeholder?: AriaInputProps["placeholder"];
}

export function AutocompleteSearchField({ className, placeholder, ...props }: SearchInputProps) {
  return (
    <AriaSearchField
      className="group sticky flex items-center border-neutral-200 border-b px-2 text-sm"
      aria-label="Search"
      autoFocus
      {...props}
    >
      <SearchIcon aria-hidden className="size-3.5 text-neutral-400" />
      <AriaInput
        className={classNames(
          "min-w-0 flex-1 border-none px-2 py-1.5 outline-hidden placeholder:text-neutral-400 [&::-webkit-search-cancel-button]:hidden",
          className
        )}
        placeholder={placeholder}
      />
      <AriaButton
        className={classNames(
          "inline-flex rounded-full p-1 opacity-70 transition-all",
          "hover:bg-neutral-200 hover:opacity-100",
          "data-disabled:pointer-events-none",
          "group-data-empty:invisible"
        )}
      >
        <XIcon aria-hidden className="size-3.5" />
      </AriaButton>
    </AriaSearchField>
  );
}
