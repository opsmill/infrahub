import { SearchIcon, XIcon } from "lucide-react";
import type React from "react";
import {
  Autocomplete as AriaAutocomplete,
  type AutocompleteProps as AriaAutocompleteProps,
  Input as AriaInput,
  type InputProps as AriaInputProps,
  SearchField as AriaSearchField,
  type SearchFieldProps as AriaSearchFieldProps,
  useFilter,
} from "react-aria-components";
import { cn } from "tailwind-variants";

import { Button } from "../button/button";

interface AutocompleteSearchFieldProps extends AriaSearchFieldProps {
  placeholder?: AriaInputProps["placeholder"];
}

function AutocompleteSearchField({
  className,
  placeholder,
  ...props
}: AutocompleteSearchFieldProps) {
  return (
    <AriaSearchField
      className={cn("group flex items-center overflow-hidden text-sm", className)}
      aria-label="Search"
      autoFocus
      {...props}
    >
      <SearchIcon aria-hidden className="m-2 size-3.5 text-subtle-muted" />
      <AriaInput
        className="min-w-0 flex-1 border-none outline-hidden placeholder:text-subtle-muted [&::-webkit-search-cancel-button]:hidden"
        placeholder={placeholder}
      />
      <Button
        slot="remove"
        variant="ghost"
        shape="square"
        size="xxs"
        className="opacity-50 hover:opacity-100 group-data-empty:invisible"
      >
        <XIcon />
      </Button>
    </AriaSearchField>
  );
}

export interface AutocompleteProps extends AriaAutocompleteProps {
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
        <div className="sticky flex w-full items-center gap-0 overflow-hidden border-border-strong border-b pr-1">
          <AutocompleteSearchField placeholder="Search..." className="grow" />
          {suffix}
        </div>
        {children}
      </div>
    </AriaAutocomplete>
  );
}
