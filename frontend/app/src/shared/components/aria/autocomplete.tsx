import { Button } from "@infrahub/ui";
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
        <Row className="sticky w-full gap-0 overflow-hidden border-neutral-300 border-b pr-1">
          <AutocompleteSearchField placeholder="Search..." className="grow" />
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
      className={classNames("group flex items-center text-sm", className)}
      aria-label="Search"
      autoFocus
      {...props}
    >
      <SearchIcon aria-hidden className="m-2 size-3.5 text-neutral-400" />
      <AriaInput
        className="min-w-0 flex-1 border-none outline-hidden placeholder:text-neutral-400 [&::-webkit-search-cancel-button]:hidden"
        placeholder={placeholder}
      />
      <Button
        slot="remove"
        variant="ghost"
        shape="square"
        size="xxs"
        className="group-data-empty:invisible"
      >
        <XIcon />
      </Button>
    </AriaSearchField>
  );
}
