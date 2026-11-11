import { cva } from "class-variance-authority";

const stickyCellShadowVariants = cva(
  "pointer-events-none absolute top-0 bottom-0 w-4 bg-linear-to-r",
  {
    variants: {
      side: {
        left: "-right-4 from-gray-500/10 to-transparent dark:from-black/40",
        right: "-left-4 from-transparent to-gray-500/10 dark:to-black/40",
      },
    },
  }
);

export interface StickyCellShadowProps {
  side: "left" | "right";
}

export function StickyCellShadow({ side }: StickyCellShadowProps) {
  return <div className={stickyCellShadowVariants({ side })} />;
}
