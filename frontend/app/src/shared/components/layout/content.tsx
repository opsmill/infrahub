import type { HTMLAttributes, ReactNode } from "react";

import { Retry } from "@/shared/components/buttons/retry";
import { Badge } from "@/shared/components/ui/badge";
import { Card, type CardProps } from "@/shared/components/ui/card";
import { classNames } from "@/shared/utils/common";

const ContentRoot = ({ className, ...props }: HTMLAttributes<HTMLElement>) => {
  return <main className={classNames("h-full overflow-auto", className)} {...props} />;
};

type ContentTitleProps = {
  children?: ReactNode;
  title?: ReactNode;
  description?: ReactNode;
  reload?: () => void;
  isReloadLoading?: boolean;
  className?: string;
};

export const ContentTitle = ({
  children,
  description,
  isReloadLoading,
  reload,
  title,
  className,
  ...props
}: ContentTitleProps) => {
  return (
    <header
      className={classNames(
        "flex min-h-[4rem] items-center border-gray-200 border-b bg-white px-4",
        className
      )}
      {...props}
    >
      <div className="flex flex-col gap-0.5 overflow-hidden pr-2">
        {title && (
          <div className="flex items-center gap-1 font-semibold">
            <div className="truncate">{title}</div>
            {reload && <Retry isLoading={isReloadLoading} onClick={reload} />}
          </div>
        )}
        {description && <div className="truncate text-sm">{description}</div>}
      </div>
      {children}
    </header>
  );
};

export const ContentCard = ({ className, ...props }: CardProps) => {
  return <Card className={classNames("overflow-auto p-0", className)} {...props} />;
};

export type ContentCardTitleProps = {
  title?: ReactNode;
  description?: ReactNode;
  end?: ReactNode;
  badgeContent?: ReactNode;
  reload?: () => void;
  isReloadLoading?: boolean;
  className?: string;
};

export const ContentCardTitle = ({
  badgeContent,
  description,
  isReloadLoading,
  reload,
  title,
  className,
  end,
  ...props
}: ContentCardTitleProps) => {
  return (
    <header className={classNames("flex items-center border-gray-200 border-b p-5", className)} {...props}>
      <div className="flex flex-1 flex-col gap-0.5 overflow-hidden">
        {title && (
          <div className="flex items-center gap-2 font-bold text-xl">
            <h1 className="truncate">{title}</h1>
            {!!badgeContent && <Badge className="text-sm">{badgeContent}</Badge>}
            {reload && <Retry isLoading={isReloadLoading} onClick={reload} />}
          </div>
        )}
        {description && <div className="truncate text-neutral-600 text-sm">{description}</div>}
      </div>
      {end}
    </header>
  );
};

const Content = Object.assign(ContentRoot, {
  Title: ContentTitle,
  Root: ContentRoot,
  Card: ContentCard,
  CardTitle: ContentCardTitle,
});

export default Content;
