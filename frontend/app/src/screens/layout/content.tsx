import { Retry } from "@/components/buttons/retry";
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

export const Content = Object.assign(ContentRoot, {
  Title: ContentTitle,
  Root: ContentRoot,
  Card: ContentCard,
});

export default Content;
