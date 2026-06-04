import { Button, type ButtonProps } from "../button/button";

export type IconButtonProps = Omit<ButtonProps, "aria-label"> & {
  "aria-label": string;
};

/** Square, ghost-by-default icon button. Requires an aria-label for accessibility. */
export function IconButton({
  variant = "ghost",
  size = "sm",
  shape = "square",
  ...props
}: IconButtonProps) {
  return <Button variant={variant} size={size} shape={shape} {...props} />;
}
