import { CardWithBorder } from "../../components/ui/card";
import { Legend, Pie, PieChart, ResponsiveContainer, Tooltip as ChartTooltip } from "recharts";

type PrefixUsageChartProps = {
  usagePercentage: number;
};

export function PrefixUsageChart({ usagePercentage }: PrefixUsageChartProps) {
  const data = [
    { name: "Used", usagePercentage: usagePercentage, fill: "#E5484D" },
    { name: "Available", usagePercentage: 100 - usagePercentage, fill: "#5BB98C" },
  ];

  return (
    <CardWithBorder className="max-w-xs">
      <header className="bg-neutral-100 p-2 font-semibold text-sm">IP Availability</header>
      <ResponsiveContainer height={207}>
        <PieChart title="usage">
          <Pie data={data} nameKey="name" dataKey="usagePercentage" />
          <ChartTooltip />
          <Legend
            iconType="circle"
            iconSize={8}
            formatter={(value) => <span className="text-gray-600 text-sm">{value}</span>}
          />
        </PieChart>
      </ResponsiveContainer>
    </CardWithBorder>
  );
}
