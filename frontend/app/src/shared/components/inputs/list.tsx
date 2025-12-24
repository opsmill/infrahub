import React, { useState } from "react";
import { toast } from "react-toastify";

import { Button } from "@/shared/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Badge } from "@/shared/components/ui/badge";
import { Input } from "@/shared/components/ui/input";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

export interface ListProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange" | "value"> {
  defaultValue?: string[];
  value?: string[];
  onChange?: (value: string[]) => void;
}

export const List = React.forwardRef<HTMLInputElement, ListProps>(
  ({ defaultValue = [], value, onChange, className, disabled, ...props }, ref) => {
    const [internalValue, setInternalValue] = useState<string[]>(defaultValue);
    const items = value ?? internalValue;

    const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
      if (event.key === "Enter") {
        event.preventDefault();
        event.stopPropagation();

        const trimmedItem = event.currentTarget.value.trim();
        if (!trimmedItem) return;

        if (items.includes(trimmedItem)) {
          toast(<Alert message="Item already exists in the list" type={ALERT_TYPES.INFO} />);
          return;
        }

        const newValue = [...items, trimmedItem];
        onChange?.(newValue);
        setInternalValue(newValue);

        event.currentTarget.value = "";
      }
    };

    const handleDelete = (itemToDelete: string) => {
      if (disabled) return;

      const newValue = items.filter((item) => item !== itemToDelete);
      onChange?.(newValue);
      setInternalValue(newValue);
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

        <ListItems items={items} disabled={disabled} onDelete={handleDelete} />
      </div>
    );
  }
);

const ListItems = ({
  items,
  disabled,
  onDelete,
}: {
  items: string[];
  disabled?: boolean;
  onDelete: (item: string) => void;
}) => {
  return (
    <div
      className={classNames(
        inputStyle,
        "flex-wrap gap-1.5",
        disabled && "cursor-not-allowed bg-gray-100"
      )}
    >
      {items.length > 0 ? (
        items.map((item) => (
          <Badge
            key={item}
            className={classNames(
              "gap-1.5 py-0 font-normal text-sm",
              disabled && "cursor-not-allowed bg-gray-200 opacity-70"
            )}
          >
            <span>{item}</span>
            {!disabled && (
              <Button
                size="icon"
                variant="ghost"
                onClick={() => onDelete(item)}
                className="h-4 w-4 text-gray-500 hover:text-gray-800"
                aria-label={`Remove ${item}`}
              >
                &times;
              </Button>
            )}
          </Badge>
        ))
      ) : (
        <span className="mx-auto text-gray-400 italic">Empty list</span>
      )}
    </div>
  );
};
