import { forwardRef, type HTMLAttributes } from "react";

import { classNames } from "@/shared/utils/common";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {}

export const Card = forwardRef<HTMLDivElement, CardProps>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={classNames(
      "rounded-xl border border-gray-200 bg-white p-3",
      "dark:border-slate-600 dark:bg-slate-700",
      className
    )}
    {...props}
  />
));

export interface CardWithBorderProps extends HTMLAttributes<HTMLDivElement> {
  contentClassName?: string;
}

const CardWithBorderRoot = forwardRef<HTMLDivElement, CardWithBorderProps>(
  ({ children, className, contentClassName, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={classNames(
          "overflow-hidden rounded-lg border border-gray-200 bg-white p-3",
          "dark:border-slate-600 dark:bg-slate-700",
          className
        )}
        {...props}
      >
        <div
          className={classNames(
            "flex h-full w-full flex-col overflow-auto rounded-md border border-gray-200",
            "dark:border-slate-600",
            contentClassName
          )}
        >
          {children}
        </div>
      </div>
    );
  }
);

const CardWithBorderTitle = forwardRef<HTMLElement, HTMLAttributes<HTMLElement>>(
  ({ className, ...props }, ref) => (
    <header
      ref={ref}
      className={classNames(
        "rounded-t bg-neutral-100 p-2 font-semibold text-sm",
        "dark:bg-slate-600",
        className
      )}
      {...props}
    />
  )
);

export const CardWithBorder = Object.assign(CardWithBorderRoot, {
  Title: CardWithBorderTitle,
});
