import { HTMLAttributes, useState } from "react";
import { classNames } from "../../utils/common";
import { Button } from "../buttons/button-primitive";
import { Icon } from "@iconify-icon/react";

export const CodeViewerLimiter = ({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) => {
  const [showAllLines, setShowAllLines] = useState(false);

  return (
    <div>
      <div
        className={classNames(
          "relative overflow-hidden",
          !showAllLines && "max-h-[200px]",
          className
        )}
        {...props}>
        {children}

        {!showAllLines && (
          <div className="h-40 w-full bg-gradient-to-t from-white to-50% absolute bottom-0 z-20 pointer-events-none" />
        )}
      </div>

      {showAllLines ? (
        <Button
          variant="outline"
          size="xs"
          className="ml-24"
          onClick={() => setShowAllLines(false)}>
          <Icon icon="mdi:chevron-up" className="text-sm mr-1" />
          Hide lines
        </Button>
      ) : (
        <Button variant="outline" size="xs" className="ml-24" onClick={() => setShowAllLines(true)}>
          <Icon icon="mdi:chevron-down" className="text-sm mr-1" />
          See all lines
        </Button>
      )}
    </div>
  );
};
