import { getTextColor } from "../../utils/common";

type tColorDisplay = {
  color?: string;
  value?: string;
};

export const ColorDisplay = (props: tColorDisplay) => {
  const { color, value } = props;

  return (
    <div
      className="px-2 py-1 rounded-md flex flex-col min-w-[24px] min-h-[24px]"
      style={{
        backgroundColor: color || "",
        color: color ? getTextColor(color) : "",
      }}>
      {value}
    </div>
  );
};
