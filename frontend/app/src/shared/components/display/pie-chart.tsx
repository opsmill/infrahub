import { Cell, Pie, PieChart as RPieChart, Tooltip } from "recharts";

type PieChartProps = {
  data: any[];
  onClick?: Function;
};

const renderCustomizedTooltip = (props: any) => {
  const data = props?.payload[0] ?? {};

  if (data.name === "Empty") {
    return null;
  }

  return (
    <div className="z-50 rounded-md bg-white p-2 text-xs">
      {data.name}: {data.value}
    </div>
  );
};

export const PieChart = (props: PieChartProps) => {
  const { data, onClick } = props;

  const handleClick = () => {
    if (!onClick) return;

    onClick();
  };

  return (
    <div className={"relative"} onClick={handleClick}>
      <RPieChart width={100} height={60}>
        <Pie
          data={data}
          dataKey="value"
          outerRadius={30}
          innerRadius={20}
          startAngle={90}
          endAngle={-270}
        >
          {data.map((entry, index) => (
            <Cell key={index} className={entry.className ?? "fill-gray-200"} />
          ))}
        </Pie>

        <Tooltip content={renderCustomizedTooltip} />
      </RPieChart>
    </div>
  );
};
