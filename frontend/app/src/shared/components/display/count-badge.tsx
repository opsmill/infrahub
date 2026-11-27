import { cva, type VariantProps } from "class-variance-authority";

import { formatNumberDisplay } from "@/shared/utils/number";

const countBadgeVariants = cva(
  "inline-flex shrink-0 items-center justify-center rounded-full font-medium tabular-nums",
  {
    variants: {
      variant: {
        raised:
          "inset-shadow-raised h-5 min-w-5 border border-cyan-600/30 bg-gradient-to-b from-cyan-50 to-white px-1 text-cyan-700 text-xs shadow-xs dark:border-cyan-400/25 dark:from-cyan-400/15 dark:to-cyan-400/5 dark:text-cyan-300 dark:shadow-none",
        pill: "h-4 min-w-4 bg-content-strong px-1.5 text-foreground-muted text-xxs leading-none",
      },
    },
    defaultVariants: {
      variant: "raised",
    },
  }
);

interface CountBadgeProps extends VariantProps<typeof countBadgeVariants> {
  count: number;
  hasMore?: boolean;
}

export function CountBadge({ count, hasMore = false, variant }: CountBadgeProps) {
  return (
    <span className={countBadgeVariants({ variant })}>
      {formatNumberDisplay(count)}
      {hasMore && "+"}
    </span>
  );
}
