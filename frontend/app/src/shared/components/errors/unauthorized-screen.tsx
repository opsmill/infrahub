import { Icon } from "@iconify-icon/react";
import type { ReactElement } from "react";

import Accordion from "@/shared/components/display/accordion";
import { classNames } from "@/shared/utils/common";

type tUnauthorized = {
  className?: string;
  message?: string;
  icon?: ReactElement;
};

const DEFAULT_MESSAGE = "Sorry, you are not authorized to access this view.";

export default function UnauthorizedScreen({ className, message, icon }: tUnauthorized) {
  return (
    <div className={classNames("flex flex-1 flex-col items-center justify-center p-8", className)}>
      {icon || (
        <Icon
          icon={"mdi:warning-circle-outline"}
          className="rounded-full bg-white text-3xl text-red-300"
        />
      )}

      <Accordion
        title={"You can't access this view"}
        className="flex w-full flex-col items-center text-center"
      >
        <div>{message ?? DEFAULT_MESSAGE}</div>
      </Accordion>
    </div>
  );
}
