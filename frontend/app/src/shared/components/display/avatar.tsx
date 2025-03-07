import { Spinner } from "@/shared/components/ui/spinner";
import { classNames } from "@/shared/utils/common";
import { type VariantProps, cva } from "class-variance-authority";
import { HTMLAttributes, forwardRef } from "react";

export const initials = (name: string) =>
  name
    .split(" ")
    .map((word) => word[0])
    .join("")
    .toUpperCase();

const avatarVariants = cva("rounded-full flex justify-center items-center", {
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

interface AvatarProps extends HTMLAttributes<HTMLDivElement>, VariantProps<typeof avatarVariants> {
  name?: string;
  text?: string;
  isLoading?: boolean;
}

export const Avatar = forwardRef<HTMLDivElement, AvatarProps>((props: AvatarProps, ref) => {
  const { name, text, variant, size, className, isLoading, ...otherProps } = props;

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
});
