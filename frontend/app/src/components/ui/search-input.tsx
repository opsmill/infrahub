import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import { forwardRef } from "react";
import { Input, InputProps } from "./input";
import { Spinner } from "./spinner";

interface SearchInputProps extends InputProps {
  loading?: boolean;
}
export const SearchInput = forwardRef<HTMLInputElement, SearchInputProps>(
  ({ loading, ...props }, ref) => {
    return (
      <div className="relative">
        <Icon
          icon="mdi:magnify"
          className="text-lg text-custom-blue-10 absolute inset-y-0 left-0 pl-2 flex items-center"
          aria-hidden="true"
        />

        <Input
          ref={ref}
          {...props}
          className={classNames("pl-8 leading-6 h-auto", props.className)}
        />

        {loading && <Spinner className="absolute inset-y-0 right-0 pr-2 flex items-center" />}
      </div>
    );
  }
);
