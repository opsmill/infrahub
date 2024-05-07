import {
  Legend,
  Pie,
  PieChart as PieChartPrimitive,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
} from "recharts";
import React from "react";

type PieChartProps = {
  data: Array<{ name: string; value: number }>;
  tooltipFormatter?: (value: any) => React.ReactNode;
  legendFormatter?: (name: string, value?: any) => React.ReactNode;
};
export const PieChart = ({ data, tooltipFormatter, legendFormatter }: PieChartProps) => {
  return (
    <ResponsiveContainer aspect={1} width={308}>
      <PieChartPrimitive>
        <Pie data={data} nameKey="name" dataKey="value" />
        <ChartTooltip formatter={tooltipFormatter} />
        <Legend
          iconType="circle"
          iconSize={8}
          formatter={(name, { payload }) => (
            <span className="text-gray-600 text-sm">
              {legendFormatter ? legendFormatter(name, payload?.value) : name}
            </span>
          )}
        />
      </PieChartPrimitive>
    </ResponsiveContainer>
  );
};
