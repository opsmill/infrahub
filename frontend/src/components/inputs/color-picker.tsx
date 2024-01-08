import { ColorResult, Colorful, HsvaColor } from "@uiw/react-color";
import { useState } from "react";
import { getTextColor } from "../../utils/common";
import { POPOVER_SIZE, PopOver } from "../display/popover";
import { Input } from "./input";

export const ColorPicker = (props: any) => {
  const { value, onChange } = props;

  const [hsva, setHsva] = useState<HsvaColor>(); // Used for colorful
  const [hex, setHex] = useState(value); // Used for input

  const handleChange = (newValue: ColorResult) => {
    setHsva(newValue.hsva);
    setHex(newValue.hex);
    onChange(newValue.hex);
  };

  const getInputStyle = () => {
    const textColor = getTextColor(hex);

    return {
      backgroundColor: hex,
      color: textColor,
    };
  };

  const PopOverButton = <Input value={hex} style={getInputStyle()} className="flex-1 mt-2" />;

  return (
    <div className="">
      <PopOver
        buttonComponent={PopOverButton}
        title={"Select a color"}
        height={POPOVER_SIZE.NONE}
        width={POPOVER_SIZE.NONE}
        className="right-">
        {() => (
          <div className="p-2">
            <Colorful color={hsva} onChange={handleChange} disableAlpha />
          </div>
        )}
      </PopOver>
    </div>
  );
};
