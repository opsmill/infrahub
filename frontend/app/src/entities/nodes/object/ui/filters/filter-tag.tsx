import { Icon } from "@iconify-icon/react";
import type React from "react";
import { Button, Tag, type TagProps } from "react-aria-components";

import { focusVisibleStyle } from "@/shared/components/aria/style-rac";
import { classNames } from "@/shared/utils/common";

interface FilterTagProps extends TagProps {
  label: React.ReactNode;
  value: React.ReactNode;
  condition?: string;
  onEdit?: () => void;
}

export function FilterTag({ label, value, condition, onEdit, ...props }: FilterTagProps) {
  return (
    <Tag
      className={classNames(
        focusVisibleStyle,
        "group inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-gray-300 bg-neutral-100 px-1 text-gray-600 text-sm",
        "cursor-default",
        "data-hovered:border-custom-blue-700 data-hovered:bg-gray-100"
      )}
      textValue={`${label} ${condition ?? "contains"} ${value}`}
      {...props}
    >
      <button
        type="button"
        className={classNames(
          "ml-1.5 inline-flex items-center gap-1.5 bg-transparent p-0",
          onEdit ? "cursor-pointer" : "cursor-default"
        )}
        onClick={(e) => {
          if (onEdit) {
            e.stopPropagation();
            onEdit();
          }
        }}
      >
        <span>{label}</span>
        {condition && <span className="text-gray-400">{condition}</span>}
        <div className="h-6 w-px self-stretch bg-gray-300" />
        <span className="inline-flex items-center font-medium text-custom-blue-700">{value}</span>
      </button>
      <Button slot="remove" className="inline-flex cursor-pointer items-center bg-transparent p-0">
        <Icon
          icon="mdi:close-circle-outline"
          className="text-base text-gray-400 hover:text-custom-blue-700"
        />
      </Button>
    </Tag>
  );
}
