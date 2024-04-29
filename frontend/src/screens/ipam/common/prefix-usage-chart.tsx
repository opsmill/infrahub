import ProgressBar from "../../../components/stats/progress-bar";
import { CardWithBorder } from "../../../components/ui/card";

type PrefixUsageChartProps = {
  usagePercentage: number;
};

export function PrefixUsageChart({ usagePercentage }: PrefixUsageChartProps) {
  return (
    <CardWithBorder className="flex-1">
      <CardWithBorder.Title>IP Usage</CardWithBorder.Title>

      <div className="p-4">
        <ProgressBar value={usagePercentage} displayValue />
      </div>
    </CardWithBorder>
  );
}
