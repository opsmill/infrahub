import { Retry } from "@/components/buttons/retry";
import { Badge } from "@/components/ui/badge";
import { Card, CardProps } from "@/components/ui/card";
import { classNames } from "@/utils/common";
import { HTMLAttributes, ReactNode } from "react";

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
        "min-h-[4rem] bg-custom-white flex items-center px-4 border-b",
        className
      )}
      {...props}
    >
      <div className="flex flex-col gap-0.5 overflow-hidden pr-2">
        {title && (
          <div className="font-semibold flex items-center gap-1">
            <div className="truncate">{title}</div>
            {reload && <Retry isLoading={isReloadLoading} onClick={reload} />}
          </div>
        )}
        {description && <div className="text-sm truncate">{description}</div>}
      </div>
      {children}
    </header>
  );
};

export const ContentCard = ({ className, ...props }: CardProps) => {
  return <Card className={classNames("p-0 m-2 overflow-hidden", className)} {...props} />;
};

export type ContentCardTitleProps = {
  title?: ReactNode;
  subtitle?: ReactNode;
  description?: ReactNode;
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
  ...props
}: ContentCardTitleProps) => {
  return (
    <header className={classNames("flex items-center p-5", className)} {...props}>
      <div className="flex flex-col gap-0.5 overflow-hidden">
        {title && (
          <div className="font-bold text-xl flex items-center gap-2">
            <div className="truncate">{title}</div>
            {badgeContent && <Badge className="text-sm">{badgeContent}</Badge>}
            {reload && <Retry isLoading={isReloadLoading} onClick={reload} />}
          </div>
        )}
        {description && <div className="text-sm truncate">{description}</div>}
      </div>
    </header>
  );
};

export const Content = Object.assign(ContentRoot, {
  Title: ContentTitle,
  Root: ContentRoot,
  Card: ContentCard,
  CardTitle: ContentCardTitle,
});

export default Content;
