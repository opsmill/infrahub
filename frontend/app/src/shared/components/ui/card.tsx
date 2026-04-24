import type React from "react";

import { classNames } from "@/shared/utils/common";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  ref?: React.Ref<HTMLDivElement>;
}

export function Card({ className, ref, ...props }: CardProps) {
  return (
    <div
      ref={ref}
      className={classNames("rounded-xl border border-gray-200 bg-white p-3", className)}
      {...props}
    />
  );
}

export interface CardWithBorderProps extends React.HTMLAttributes<HTMLDivElement> {
  ref?: React.Ref<HTMLDivElement>;
  contentClassName?: string;
}

function CardWithBorderRoot({
  children,
  className,
  contentClassName,
  ref,
  ...props
}: CardWithBorderProps) {
  return (
    <div
      ref={ref}
      className={classNames(
        "overflow-hidden rounded-lg border border-gray-200 bg-white p-3",
        className
      )}
      {...props}
    >
      <div
        className={classNames(
          "flex h-full w-full flex-col overflow-auto rounded-md border border-gray-200",
          contentClassName
        )}
      >
        {children}
      </div>
    </div>
  );
}

interface CardWithBorderTitleProps extends React.HTMLAttributes<HTMLDivElement> {
  ref?: React.Ref<HTMLDivElement>;
}

function CardWithBorderTitle({ className, ref, ...props }: CardWithBorderTitleProps) {
  return (
    <div
      ref={ref}
      role="heading"
      className={classNames("rounded-t bg-neutral-100 px-3 py-2 font-semibold text-sm", className)}
      {...props}
    />
  );
}

export const CardWithBorder = Object.assign(CardWithBorderRoot, {
  Title: CardWithBorderTitle,
});
