import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { MAX_VALUE_LENGTH_DISPLAY } from "../../config/constants";
import { BUTTON_TYPES, Button } from "../buttons/button";

type tPasswordDisplayProps = {
  value: string;
};

export const PasswordDisplay = (props: tPasswordDisplayProps) => {
  const { value } = props;

  const [display, setDisplay] = useState(false);

  const displayButton = (
    <Button buttonType={BUTTON_TYPES.INVISIBLE} onClick={() => setDisplay(!display)}>
      <Icon icon={display ? "mdi:eye" : "mdi:eye-off"} className="text-gray-600" />
    </Button>
  );

  if (display) {
    return (
      <div className="flex items-center">
        <div className="mr-1">{displayButton}</div>

        <div>
          {value?.length > MAX_VALUE_LENGTH_DISPLAY
            ? `${value.substr(0, MAX_VALUE_LENGTH_DISPLAY)}...`
            : value}
        </div>
      </div>
    );
  }

  const passwordCircles = Array.from(Array(value.length)).map((value: null, index: number) => (
    <Icon key={index} icon={"mdi:circle-medium"} className="text-gray-900" />
  ));

  return (
    <div className="flex items-center">
      <div>{displayButton}</div>

      <div className="flex items-center">{passwordCircles}</div>
    </div>
  );
};
