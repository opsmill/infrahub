import { Tooltip } from "@infrahub/ui";

import { getTextColor } from "@/shared/utils/common";

type tColorDisplay = {
  color?: string | null;
  value?: string | null;
  description?: string | null;
};

export const ColorDisplay = (props: tColorDisplay) => {
  const { color, value, description } = props;

  if (description) {
    return (
      <Tooltip message={description} nonInteractiveTrigger>
        <div
          className="inline-flex min-h-6 min-w-6 flex-col rounded-md px-2 py-1"
          style={{
            backgroundColor: color || "",
            color: color ? getTextColor(color) : "",
          }}
        >
          {value}
        </div>
      </Tooltip>
    );
  }

  return (
    <div
      className="inline-flex min-h-6 min-w-6 flex-col rounded-md px-2 py-1"
      style={{
        backgroundColor: color || "",
        color: color ? getTextColor(color) : "",
      }}
    >
      {value}
    </div>
  );
};
