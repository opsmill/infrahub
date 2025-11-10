import { Icon } from "@iconify-icon/react";
import { forwardRef } from "react";

import { classNames } from "@/shared/utils/common";

import { Input, type InputProps } from "./input";
import { Spinner } from "./spinner";

export interface SearchInputProps extends InputProps {
  loading?: boolean;
  containerClassName?: string;
}
export const SearchInput = forwardRef<HTMLInputElement, SearchInputProps>(
  ({ containerClassName, className, loading, ...props }, ref) => {
    return (
      <div className={classNames("relative", containerClassName)}>
        <Icon
          icon="mdi:magnify"
          className="absolute inset-y-0 left-0 flex items-center pl-2 text-custom-blue-10 text-lg"
          aria-hidden="true"
        />

        <Input ref={ref} {...props} className={classNames("h-auto pl-8", className)} />

        {loading && (
          <Spinner
            className="absolute inset-y-0 right-0 flex items-center pr-2"
            data-testid="objects-search-input-loader"
          />
        )}
      </div>
    );
  }
);
