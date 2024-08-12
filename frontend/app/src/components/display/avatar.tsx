import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { classNames } from "@/utils/common";
import { cva, type VariantProps } from "class-variance-authority";

export const initials = (name?: string) =>
  name
    ? name
        .split(" ")
        .map((word) => word[0])
        .join("")
        .toUpperCase()
    : "-";

const avatarVariants = cva("rounded-full flex justify-center items-center", {
  variants: {
    variant: {
      primary: "bg-custom-blue-200 text-custom-white",
      active: "bg-green-300 text-green-700",
    },
    size: {
      default: "h-12 w-12",
      sm: "h-6 w-6 text-xs",
    },
  },
  defaultVariants: {
    variant: "primary",
    size: "default",
  },
});

interface tAvatar extends VariantProps<typeof avatarVariants> {
  name?: string;
  className?: string;
  isLoading?: boolean;
}

export const Avatar = (props: tAvatar) => {
  const { name, variant, size, className, isLoading, ...otherProps } = props;

  if (isLoading) {
    return (
      <div className={classNames(avatarVariants({ variant, size, className }), className ?? "")}>
        <LoadingScreen colorClass={"custom-white"} size={16} hideText />
      </div>
    );
  }

  return (
    <div className={classNames(avatarVariants({ variant, size, className }))} {...otherProps}>
      {initials(name)}
    </div>
  );
};
