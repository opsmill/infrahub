import { cva, type VariantProps } from "class-variance-authority";

import { classNames } from "@/shared/utils/common";

export const pushableItemContainerStyle = "relative flex cursor-pointer select-none outline-hidden";

interface PushableItemEdgeProps {
  isPressed: boolean;
}

export function PushableItemEdge({ isPressed }: PushableItemEdgeProps) {
  return (
    <span
      className={classNames(
        "absolute inset-0 rounded-lg border-stone-400 border-b bg-pushable-edge-gradient shadow-xs",
        isPressed && "shadow-none"
      )}
    />
  );
}

const pushableItemStyles = cva(
  "flex w-full min-w-40 items-center gap-2 rounded-lg border px-2 py-1 text-sm text-stone-600 transition-transform will-change-transform",
  {
    variants: {
      variant: {
        default: "border-white bg-white shadow-xs",
        ghost: "border-transparent bg-transparent text-stone-800",
      },
      isFocused: {
        true: "-translate-y-0.75 border-stone-300 shadow-none duration-150 ease-in-out",
      },
      isPressed: {
        true: "translate-y-0 duration-80 ease-out",
      },
    },
    compoundVariants: [{ variant: "ghost", isFocused: true, class: "bg-white" }],
    defaultVariants: {
      variant: "default",
    },
  }
);

interface PushableItemProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof pushableItemStyles> {}

export function PushableItem({
  variant,
  isFocused,
  isPressed,
  className,
  ...props
}: PushableItemProps) {
  return (
    <>
      {isFocused && <PushableItemEdge isPressed={!!isPressed} />}

      <div
        className={classNames(pushableItemStyles({ variant, isFocused, isPressed }), className)}
        {...props}
      />
    </>
  );
}
