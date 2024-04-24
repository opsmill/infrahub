import { CardWithBorder } from "../../../components/ui/card";
import { PieChart } from "../../../components/stats/pie-chart";

type PrefixUsageChartProps = {
  usagePercentage: number;
};

export function PrefixUsageChart({ usagePercentage }: PrefixUsageChartProps) {
  const data = [
    { name: "available", value: 100 - usagePercentage, fill: "#5BB98C" },
    { name: "used", value: usagePercentage, fill: "#E5484D" },
  ];

  return (
    <CardWithBorder>
      <CardWithBorder.Title>IP Availability</CardWithBorder.Title>

      <PieChart
        data={data}
        tooltipFormatter={(value) => <span className="text-sm">{value}%</span>}
        legendFormatter={(name, value) => `${value}% ${name}`}
      />
    </CardWithBorder>
  );
}
