import { Tooltip } from "@/shared/components/ui/tooltip";
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
      <Tooltip enabled content={description}>
        <div
          className="inline-flex min-h-[24px] min-w-[24px] flex-col rounded-md px-2 py-1"
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
      className="inline-flex min-h-[24px] min-w-[24px] flex-col rounded-md px-2 py-1"
      style={{
        backgroundColor: color || "",
        color: color ? getTextColor(color) : "",
      }}
    >
      {value}
    </div>
  );
};
