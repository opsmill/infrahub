import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import { Row } from "@/shared/components/container";
import { Button } from "@/shared/components/ui/button";
import { MAX_PASSWORD_DOTS_DISPLAY, MAX_VALUE_LENGTH_DISPLAY } from "@/shared/config/constants";

type tPasswordDisplayProps = {
  value: string;
};

export const PasswordDisplay = (props: tPasswordDisplayProps) => {
  const { value } = props;

  const [display, setDisplay] = useState(false);

  const displayButton = (
    <Button variant="ghost" size="icon" onClick={() => setDisplay(!display)}>
      <Icon icon={display ? "mdi:eye" : "mdi:eye-off"} className="text-gray-600" />
    </Button>
  );

  if (display) {
    return (
      <Row>
        {displayButton}

        <div>
          {value?.length > MAX_VALUE_LENGTH_DISPLAY
            ? `${value.substr(0, MAX_VALUE_LENGTH_DISPLAY)}...`
            : value}
        </div>
      </Row>
    );
  }

  const passwordCircles = Array.from(
    Array(value.length < MAX_PASSWORD_DOTS_DISPLAY ? value.length : MAX_PASSWORD_DOTS_DISPLAY)
  ).map((_, index: number) => (
    <Icon key={index} icon={"mdi:circle-medium"} className="text-gray-900" />
  ));

  return (
    <Row>
      {displayButton}

      <div className="flex items-center">{passwordCircles}</div>
    </Row>
  );
};
