import React from "react";
import { toast } from "react-toastify";

import { Button } from "@/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { inputStyle } from "@/components/ui/style";
import { classNames } from "@/utils/common";

export interface ListProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange" | "value"> {
  value: string[];
  onChange: (value: string[]) => void;
}

export const List = React.forwardRef<HTMLInputElement, ListProps>(
  ({ value = [], onChange, className, disabled, ...props }, ref) => {
    const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
      if (event.key === "Enter") {
        event.preventDefault();
        event.stopPropagation();

        const trimmedItem = event.currentTarget.value.trim();
        if (!trimmedItem) return;

        if (value.includes(trimmedItem)) {
          toast(<Alert message="Item already exists in the list" type={ALERT_TYPES.INFO} />);
          return;
        }

        onChange([...value, trimmedItem]);
        event.currentTarget.value = "";
      }
    };

    const handleDelete = (itemToDelete: string) => {
      if (disabled) return;
      onChange(value.filter((item) => item !== itemToDelete));
    };

    return (
      <div>
        <Input
          ref={ref}
          placeholder="Add a new item + hit 'enter'"
          className={classNames("mb-1", className)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          {...props}
        />

        <ListItems items={value} disabled={disabled} onDelete={handleDelete} />
      </div>
    );
  }
);

const ListItems = ({
  items,
  disabled,
  onDelete,
}: { items: string[]; disabled?: boolean; onDelete: (item: string) => void }) => {
  return (
    <div
      className={classNames(
        inputStyle,
        "gap-1.5 flex-wrap",
        disabled && "cursor-not-allowed bg-gray-100"
      )}
    >
      {items.length > 0 ? (
        items.map((item) => (
          <Badge
            key={item}
            className={classNames(
              "text-sm font-normal gap-1.5 py-0",
              disabled && "opacity-70 bg-gray-200 cursor-not-allowed"
            )}
          >
            <span>{item}</span>
            {!disabled && (
              <Button
                size="icon"
                variant="ghost"
                onClick={() => onDelete(item)}
                className="text-gray-500 hover:text-gray-800 h-4 w-4"
                aria-label="Remove"
              >
                &times;
              </Button>
            )}
          </Badge>
        ))
      ) : (
        <span className="text-gray-400 italic mx-auto">Empty list</span>
      )}
    </div>
  );
};
