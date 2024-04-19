import { CardWithBorder } from "../../components/ui/card";
import { Legend, Pie, PieChart, ResponsiveContainer, Tooltip as ChartTooltip } from "recharts";

type PrefixUsageChartProps = {
  usagePercentage: number;
};

export function PrefixUsageChart({ usagePercentage }: PrefixUsageChartProps) {
  const data = [
    { name: "available", usagePercentage: 100 - usagePercentage, fill: "#5BB98C" },
    { name: "used", usagePercentage: usagePercentage, fill: "#E5484D" },
  ];

  return (
    <CardWithBorder className="max-w-xs">
      <CardWithBorder.Title>IP Availability</CardWithBorder.Title>

      <ResponsiveContainer height={208}>
        <PieChart title="usage">
          <Pie data={data} nameKey="name" dataKey="usagePercentage" />
          <ChartTooltip formatter={(value) => <span className="text-sm">{value}%</span>} />
          <Legend
            iconType="circle"
            iconSize={8}
            formatter={(value, { payload }) => (
              <span className="text-gray-600 text-sm">
                {payload && `${payload.value}%`} {value}
              </span>
            )}
          />
        </PieChart>
      </ResponsiveContainer>
    </CardWithBorder>
  );
}
