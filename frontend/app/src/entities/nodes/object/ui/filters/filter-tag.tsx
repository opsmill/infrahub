import { Icon } from "@iconify-icon/react";
import React from "react";
import { Tag, TagProps } from "react-aria-components";

import { focusVisibleStyle } from "@/shared/components/style-rac";
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
        "group text-gray-600 text-sm whitespace-nowrap bg-neutral-100 rounded-full inline-flex items-center gap-1.5 px-1 border border-gray-300 cursor-pointer",
        "data-hovered:bg-gray-100 data-hovered:border-custom-blue-700"
      )}
      textValue={`${label} contains ${value}`}
      {...props}
    >
      <span className="ml-1.5">{label}</span>
      <div className="w-px bg-gray-300 self-stretch h-6" />
      <span className="text-custom-blue-700 font-medium inline-flex items-center">{value}</span>
      <Icon
        icon="mdi:close-circle-outline"
        className="text-base text-gray-400 group-hover:text-custom-blue-700"
      />
    </Tag>
  );
}
