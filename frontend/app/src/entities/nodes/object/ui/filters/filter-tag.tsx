import { Icon } from "@iconify-icon/react";
import type React from "react";
import { Tag, type TagProps } from "react-aria-components";

import { focusVisibleStyle } from "@/shared/components/aria/style-rac";
import { classNames } from "@/shared/utils/common";

interface FilterTagProps extends TagProps {
  label: React.ReactNode;
  value: React.ReactNode;
}

export function FilterTag({ label, value, ...props }: FilterTagProps) {
  return (
    <Tag
      className={classNames(
        focusVisibleStyle,
        "group inline-flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-full border border-gray-300 bg-neutral-100 px-1 text-gray-600 text-sm",
        "data-hovered:border-custom-blue-700 data-hovered:bg-gray-100"
      )}
      textValue={`${label} contains ${value}`}
      {...props}
    >
      <span className="ml-1.5">{label}</span>
      <div className="h-6 w-px self-stretch bg-gray-300" />
      <span className="inline-flex items-center font-medium text-custom-blue-700">{value}</span>
      <Icon
        icon="mdi:close-circle-outline"
        className="text-base text-gray-400 group-hover:text-custom-blue-700"
      />
    </Tag>
  );
}
