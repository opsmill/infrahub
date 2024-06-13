import { POPOVER_SIZE, PopOver } from "@/components/display/popover";
import { Input } from "@/components/ui/input";
import { getTextColor } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import { ColorResult, Colorful, HsvaColor } from "@uiw/react-color/src/index";
import { forwardRef, useState } from "react";

export const ColorPicker = forwardRef<HTMLInputElement, any>((props, ref) => {
  const { id, value, onChange } = props;

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

  const PopOverButton = (
    <div className="w-[20px] h-[20px] bg-gradient-to-br from-custom-white via-custom-blue-50 to-custom-gray rounded-full p-2 ml-2 cursor-pointer">
      <Icon icon="mdi:eyedropper-variant text-custom-white" />
    </div>
  );

  return (
    <div className="flex items-center relative">
      <Input
        ref={ref}
        id={id}
        value={value ?? ""}
        style={getInputStyle()}
        onChange={(e) => handleInputChange(e.target.value)}
        className="flex-1"
      />
      <div className="flex">
        <PopOver
          buttonComponent={PopOverButton}
          title={"Select a color"}
          height={POPOVER_SIZE.NONE}
          width={POPOVER_SIZE.NONE}
          className="right- left-0">
          {() => (
            <div className="p-2">
              <Colorful color={hsva} onChange={handleChange} disableAlpha />
            </div>
          )}
        </PopOver>
      </div>
    </div>
  );
});
