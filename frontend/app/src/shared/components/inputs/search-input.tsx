import { Icon } from "@iconify-icon/react";
import {
  Button as AriaButton,
  type ButtonProps as AriaButtonProps,
  Group as AriaGroup,
  type GroupProps as AriaGroupProps,
  Input as AriaInput,
  type InputProps as AriaInputProps,
  SearchField as AriaSearchField,
  type SearchFieldProps as AriaSearchFieldProps,
  composeRenderProps,
} from "react-aria-components";

import { focusWithinStyle, inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

export function SearchField({ className, ...props }: AriaSearchFieldProps) {
  return (
    <AriaSearchField
      className={composeRenderProps(className, (className) => classNames("group", className))}
      {...props}
    />
  );
}

export function SearchFieldInput({ className, ...props }: AriaInputProps) {
  return (
    <AriaInput
      className={composeRenderProps(className, (className) =>
        classNames(
          "min-w-0 flex-1 border-none px-2 py-1.5 outline-hidden placeholder:text-gray-400 [&::-webkit-search-cancel-button]:hidden",
          className
        )
      )}
      {...props}
    />
  );
}

export function SearchFieldGroup({ className, ...props }: AriaGroupProps) {
  return (
    <AriaGroup
      className={composeRenderProps(className, (className) =>
        classNames(
          inputStyle,
          focusWithinStyle,
          "h-10 min-h-0 overflow-hidden",
          "data-disabled:opacity-50",
          className
        )
      )}
      {...props}
    />
  );
}

export function SearchFieldClear({ className, ...props }: AriaButtonProps) {
  return (
    <AriaButton
      className={composeRenderProps(className, (className) =>
        classNames(
          "inline-flex rounded-xs opacity-70 transition-opacity",
          "data-hovered:opacity-100",
          "data-disabled:pointer-events-none",
          "group-data-empty:invisible",
          className
        )
      )}
      {...props}
    />
  );
}

export interface SearchInputProps extends AriaSearchFieldProps {
  className?: string;
  placeholder?: AriaInputProps["placeholder"];
  onPressReset?: () => void;
}

export function SearchInput({ className, placeholder, onPressReset, ...props }: SearchInputProps) {
  return (
    <SearchField {...props} aria-label="Search">
      <SearchFieldGroup className={className}>
        <Icon icon="mdi:magnify" className="text-lg" />
        <SearchFieldInput placeholder={placeholder} />
        <SearchFieldClear onPress={onPressReset}>
          <Icon icon="mdi:close" className="text-lg" />
        </SearchFieldClear>
      </SearchFieldGroup>
    </SearchField>
  );
}
