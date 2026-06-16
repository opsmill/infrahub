import { Button, Popover, PopoverTrigger } from "@infrahub/ui";
import { Colorful, type ColorResult, type HsvaColor } from "@uiw/react-color";
import React from "react";

import { Input } from "@/shared/components/ui/input";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import { classNames, getTextColor } from "@/shared/utils/common";

export const ColorPicker = (props: any & { ref?: React.Ref<HTMLInputElement> }) => {
  const { id, disabled, value, onChange, className, ref } = props;

  const [hsva, setHsva] = React.useState<string | HsvaColor>(value ?? { h: 0, s: 0, v: 0, a: 0 }); // Used for colorfule

  const handleChange = (newValue: ColorResult) => {
    setHsva(newValue.hsva);
    onChange(newValue.hex);
  };

  const handleInputChange = (newValue: string) => {
    onChange(newValue);
  };

  const getInputStyle = () => {
    const textColor = getTextColor(value);

    return {
      backgroundColor: value,
      color: textColor,
    };
  };

  return (
    <PopoverTrigger>
      <div
        className={classNames(
          "relative flex items-center gap-2",
          disabled && "pointer-events-none opacity-50"
        )}
      >
        <Input
          disabled={disabled}
          ref={ref}
          id={id}
          value={value ?? ""}
          style={getInputStyle()}
          onChange={(e) => handleInputChange(e.target.value)}
          className={className}
        />

        <Button
          shape="circle"
          size="xxs"
          className={classNames(
            focusVisibleStyle,
            "bg-linear-to-br from-custom-white via-custom-blue-50 to-custom-gray"
          )}
        />

        <Popover>
          <Colorful color={hsva} onChange={handleChange} disableAlpha />
        </Popover>
      </div>
    </PopoverTrigger>
  );
};
