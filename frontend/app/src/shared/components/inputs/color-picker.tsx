import { Colorful, type ColorResult, type HsvaColor } from "@uiw/react-color";
import { forwardRef, useState } from "react";

import { Input } from "@/shared/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import { classNames, getTextColor } from "@/shared/utils/common";

export const ColorPicker = forwardRef<HTMLInputElement, any>((props, ref) => {
  const { id, disabled, value, onChange, portal, className } = props;

  const [hsva, setHsva] = useState<string | HsvaColor>(value ?? { h: 0, s: 0, v: 0, a: 0 }); // Used for colorfule

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

      <Popover>
        <PopoverTrigger
          className={classNames(
            focusVisibleStyle,
            "size-5 shrink-0 rounded-full bg-linear-to-br from-custom-white via-custom-blue-50 to-custom-gray"
          )}
        />

        <PopoverContent portal={portal} className="p-2">
          <Colorful color={hsva} onChange={handleChange} disableAlpha />
        </PopoverContent>
      </Popover>
    </div>
  );
});
