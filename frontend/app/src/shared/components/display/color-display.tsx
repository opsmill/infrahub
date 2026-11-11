import { Tooltip } from "@infrahub/ui";

import { classNames, getTextColor } from "@/shared/utils/common";

type tColorDisplay = {
  color?: string | null;
  value?: string | null;
  description?: string | null;
  className?: string;
};

export const ColorDisplay = ({ color, value, description, className }: tColorDisplay) => {
  const content = (
    <div
      className={classNames("inline-flex min-h-6 min-w-6 flex-col rounded-md px-2 py-1", className)}
      // The colour comes from the schema at runtime, so no utility class can express it.
      style={{
        backgroundColor: color || "",
        color: color ? getTextColor(color) : "",
      }}
    >
      {value}
    </div>
  );

  if (!description) return content;

  return (
    <Tooltip message={description} nonInteractiveTrigger>
      {content}
    </Tooltip>
  );
};
