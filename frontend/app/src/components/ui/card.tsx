import { classNames } from "@/utils/common";
import { forwardRef, HTMLAttributes } from "react";

export const Card = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={classNames("bg-custom-white rounded-lg border p-3", className)}
      {...props}
    />
  )
);

interface CardWithBorderRootProps extends HTMLAttributes<HTMLDivElement> {
  contentClassName?: string;
}

const CardWithBorderRoot = forwardRef<HTMLDivElement, CardWithBorderRootProps>(
  ({ children, className, contentClassName, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={classNames("bg-custom-white p-3 border rounded-lg overflow-hidden", className)}
        {...props}>
        <div
          className={classNames(
            "h-full w-full border rounded-md overflow-auto flex flex-col",
            contentClassName
          )}>
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
      className={classNames("bg-neutral-100 p-2 font-semibold text-sm", className)}
      {...props}
    />
  )
);

export const CardWithBorder = Object.assign(CardWithBorderRoot, {
  Title: CardWithBorderTitle,
});
