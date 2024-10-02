import { getTextColor } from "@/utils/common";
import { Tooltip } from "../ui/tooltip";

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
          className="px-2 py-1 rounded-md inline-flex flex-col min-w-[24px] min-h-[24px]"
          style={{
            backgroundColor: color || "",
            color: color ? getTextColor(color) : "",
          }}>
          {value}
        </div>
      </Tooltip>
    );
  }

  return (
    <div
      className="px-2 py-1 rounded-md inline-flex flex-col min-w-[24px] min-h-[24px]"
      style={{
        backgroundColor: color || "",
        color: color ? getTextColor(color) : "",
      }}>
      {value}
    </div>
  );
};
