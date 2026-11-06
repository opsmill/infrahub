export const formatUsagePercent = (value: number) => {
  if (value === 0) return "0%";
  if (value < 0.1) return "<0.1%";
  if (value < 10) return `${value.toFixed(1).replace(/\.0$/, "")}%`;
  return `${Math.floor(value)}%`;
};
