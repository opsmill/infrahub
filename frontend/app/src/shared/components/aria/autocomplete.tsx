import { SearchIcon, XIcon } from "lucide-react";
import type React from "react";
import {
  Autocomplete as AriaAutocomplete,
  type AutocompleteProps as AriaAutocompleteProps,
  Button as AriaButton,
  Input as AriaInput,
  type InputProps as AriaInputProps,
  SearchField as AriaSearchField,
  type SearchFieldProps as AriaSearchFieldProps,
  useFilter,
} from "react-aria-components";

import { Row } from "@/shared/components/container";
import { classNames } from "@/shared/utils/common";

interface AutocompleteProps extends AriaAutocompleteProps {
  suffix?: React.ReactNode;
}

export function Autocomplete({
  filter,
  onInputChange,
  children,
  suffix,
  ...props
}: AutocompleteProps) {
  const { contains } = useFilter({ sensitivity: "base" });
  // When onInputChange is provided, items are controlled externally (server-side search) — skip client-side filtering.
  const resolvedFilter = filter ?? (onInputChange ? undefined : contains);

  return (
    <AriaAutocomplete filter={resolvedFilter} onInputChange={onInputChange} {...props}>
      <div className="max-h-[inherit] overflow-hidden">
        <Row className="sticky w-full gap-0 overflow-hidden border-neutral-300 border-b">
          <AutocompleteSearchField placeholder="Search..." />
          {suffix}
        </Row>
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
      className="group flex items-center overflow-hidden text-sm"
      aria-label="Search"
      autoFocus
      {...props}
    >
      <SearchIcon aria-hidden className="m-2 size-3.5 text-neutral-400" />
      <AriaInput
        className={classNames(
          "min-w-0 flex-1 border-none outline-hidden placeholder:text-neutral-400 [&::-webkit-search-cancel-button]:hidden",
          className
        )}
        placeholder={placeholder}
      />
      <AriaButton
        className={classNames(
          "m-1 inline-flex rounded-full p-1 opacity-70 transition-all",
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
