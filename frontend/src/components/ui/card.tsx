import { forwardRef, HTMLAttributes } from "react";
import { classNames } from "../../utils/common";

export const Card = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={classNames("bg-custom-white rounded-lg border border-gray-300 p-3", className)}
      {...props}
    />
  )
);

const CardWithBorderRoot = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ children, className }, ref) => {
    return (
      <div ref={ref} className={classNames("border rounded-lg", className)}>
        <div className="border rounded-md m-3 overflow-hidden">{children}</div>
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
