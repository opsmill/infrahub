import { cva, type VariantProps } from "class-variance-authority";
import type React from "react";

import { Spinner } from "@/shared/components/ui/spinner";
import { classNames } from "@/shared/utils/common";

export const initials = (name: string) =>
  name
    .split(" ")
    .map((word) => word[0])
    .join("")
    .toUpperCase();

const avatarVariants = cva("flex items-center justify-center rounded-full", {
  variants: {
    variant: {
      primary: "bg-custom-blue-200 text-custom-white",
      active: "bg-green-300 text-green-700",
    },
    size: {
      default: "h-12 w-12",
      sm: "h-6 w-6 text-xs",
      md: "h-8 w-8 text-xs",
    },
  },
  defaultVariants: {
    variant: "primary",
    size: "default",
  },
});

interface AvatarProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof avatarVariants> {
  name?: string | null;
  text?: string;
  isLoading?: boolean;
  ref?: React.Ref<HTMLDivElement>;
}

export const Avatar = (props: AvatarProps) => {
  const { name, text, variant, size, className, isLoading, ref, ...otherProps } = props;

  if (isLoading) {
    return (
      <div className={classNames(avatarVariants({ variant, size, className }), className ?? "")}>
        <Spinner />
      </div>
    );
  }

  return (
    <div
      ref={ref}
      className={classNames(avatarVariants({ variant, size, className }))}
      {...otherProps}
    >
      {name && initials(name)}
      {text}
      {!name && !text && "-"}
    </div>
  );
};
