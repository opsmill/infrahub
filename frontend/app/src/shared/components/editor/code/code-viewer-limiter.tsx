import { Icon } from "@iconify-icon/react";
import { HTMLAttributes, useState } from "react";

import { Button } from "@/shared/components/buttons/button-primitive";
import { classNames } from "@/shared/utils/common";

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
        {...props}
      >
        {children}

        {!showAllLines && (
          <div className="pointer-events-none absolute bottom-0 z-20 h-40 w-full bg-linear-to-t from-white to-50%" />
        )}
      </div>

      {showAllLines ? (
        <Button
          variant="outline"
          size="xs"
          className="ml-24"
          onClick={() => setShowAllLines(false)}
        >
          <Icon icon="mdi:chevron-up" className="mr-1 text-sm" />
          Hide lines
        </Button>
      ) : (
        <Button variant="outline" size="xs" className="ml-24" onClick={() => setShowAllLines(true)}>
          <Icon icon="mdi:chevron-down" className="mr-1 text-sm" />
          See all lines
        </Button>
      )}
    </div>
  );
};
