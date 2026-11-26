interface CountBadgeProps {
  count: number;
}

export function CountBadge({ count }: CountBadgeProps) {
  return (
    <span className="inset-shadow-raised inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full border border-cyan-600/30 bg-gradient-to-b from-cyan-50 to-white px-1 font-medium text-cyan-700 text-xs tabular-nums shadow-xs dark:border-cyan-400/25 dark:from-cyan-400/15 dark:to-cyan-400/5 dark:text-cyan-300 dark:shadow-none">
      {count}
    </span>
  );
}
