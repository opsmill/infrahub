import { LinkButton, type LinkButtonProps } from "@infrahub/ui";

import { classNames } from "@/shared/utils/common";

export interface LinkPillProps extends Omit<LinkButtonProps, "className"> {
  className?: string;
}

export function LinkPill({ className, ...props }: LinkPillProps) {
  return (
    <LinkButton
      variant="input"
      size="sm"
      className={classNames(
        "rounded-full border-border pr-2.5 hover:border-ring hover:underline dark:border-white/10 dark:bg-white/5 dark:shadow-none dark:hover:border-ring",
        className
      )}
      {...props}
    />
  );
}
