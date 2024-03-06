import { Cell, Pie, PieChart as RPieChart, Tooltip } from "recharts";

type tPieChart = {
  data: any[];
  children?: any;
};

// const RADIAN = Math.PI / 180;

// const renderCustomizedLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, value }) => {
//   const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
//   const x = cx + radius * Math.cos(-midAngle * RADIAN);
//   const y = cy + radius * Math.sin(-midAngle * RADIAN);

//   return (
//     <text
//       x={x}
//       y={y}
//       textAnchor="middle"
//       dominantBaseline="central"
//       className="text-xxs fill-custom-white">
//       {value}
//     </text>
//   );
// };

const renderCustomizedTooltip = (props: any) => {
  const data = props?.payload[0] ?? {};

  if (data.name === "Empty") {
    return null;
  }

  return (
    <text className="text-xs bg-custom-white p-2 rounded-md">
      {data.name}: {data.value}
    </text>
  );
};

export const PieChart = (props: tPieChart) => {
  const { data, children } = props;

  return (
    <div className="relative">
      <RPieChart width={100} height={60}>
        <Tooltip content={renderCustomizedTooltip} />
        <Pie
          data={data}
          dataKey="value"
          cx="50%"
          cy="50%"
          outerRadius={30}
          innerRadius={20}
          startAngle={90}
          endAngle={-270}
          // label={renderCustomizedLabel}
          labelLine={false}>
          {data.map((entry, index) => (
            <Cell key={index} className={entry.className ?? "fill-gray-200"} />
          ))}
        </Pie>
      </RPieChart>

      <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 flex items-center justify-center">
        {children}
      </div>
    </div>
  );
};
