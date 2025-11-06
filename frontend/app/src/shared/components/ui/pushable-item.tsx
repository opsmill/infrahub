import { cva, type VariantProps } from "class-variance-authority";
import type React from "react";

import { classNames } from "@/shared/utils/common";

export const pushableItemContainerStyle =
  "relative flex cursor-pointer select-none outline-hidden rounded-lg";
interface PushableItemEdgeProps {
  isPressed: boolean;
  isFocusVisible: boolean;
}

export function PushableItemEdge({ isPressed, isFocusVisible }: PushableItemEdgeProps) {
  return (
    <span
      aria-hidden="true"
      className={classNames(
        "absolute inset-0 rounded-[inherit] border-stone-400 border-b bg-pushable-edge-gradient shadow-xs",
        isPressed && "shadow-none",
        isFocusVisible && "border-custom-blue-600 shadow-custom-blue-600/25"
      )}
    />
  );
}

const pushableItemStyles = cva(
  "flex w-full items-center gap-2 rounded-[inherit] border px-2 py-1 text-sm text-stone-700 transition-transform will-change-transform",
  {
    variants: {
      variant: {
        default: "border-white bg-white shadow-xs",
        ghost: "border-transparent bg-transparent",
      },
      isElevated: {
        true: "-translate-y-0.75 border-stone-200 shadow-none duration-150 ease-in-out",
      },
      isPressed: {
        true: "translate-y-0 duration-80 ease-out",
      },
    },
    compoundVariants: [{ variant: "ghost", isElevated: true, class: "bg-white" }],
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface PushableItemProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof pushableItemStyles> {
  isFocusVisible?: boolean;
}

export function PushableItem({
  variant,
  isElevated,
  isPressed,
  className,
  isFocusVisible,
  ...props
}: PushableItemProps) {
  return (
    <>
      {isElevated && <PushableItemEdge isFocusVisible={!!isFocusVisible} isPressed={!!isPressed} />}

      <div
        className={classNames(pushableItemStyles({ variant, isElevated, isPressed }), className)}
        {...props}
      />
    </>
  );
}
