import { Icon } from "@iconify-icon/react";
import { ColorResult, Colorful, HsvaColor } from "@uiw/react-color";
import { useState } from "react";
import { getTextColor } from "../../utils/common";
import { POPOVER_SIZE, PopOver } from "../display/popover";
import { Input } from "./input";

export const ColorPicker = (props: any) => {
  const { value, onChange } = props;

  const [hsva, setHsva] = useState<string | HsvaColor>(value ?? { h: 0, s: 0, v: 0, a: 0 }); // Used for colorfule
  const [hex, setHex] = useState(value); // Used for input

  const handleChange = (newValue: ColorResult) => {
    setHsva(newValue.hsva);
    setHex(newValue.hex);
    onChange(newValue.hex);
  };

  const handleInputChange = (newValue: string) => {
    setHex(newValue);
    onChange(newValue);
  };

  const getInputStyle = () => {
    const textColor = getTextColor(hex);

    return {
      backgroundColor: hex,
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
      <Input value={hex} style={getInputStyle()} onChange={handleInputChange} className="flex-1" />
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
};
