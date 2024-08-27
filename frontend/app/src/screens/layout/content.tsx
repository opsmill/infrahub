import { Retry } from "@/components/buttons/retry";
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
      {...props}>
      <div className="flex flex-col gap-0.5 overflow-hidden pr-2">
        {title && (
          <div className="font-semibold flex items-center gap-2">
            <div className="truncate">{title}</div>
            {reload && <Retry isLoading={isReloadLoading} onClick={reload} />}
          </div>
        )}
        {description && <p className="text-sm truncate">{description}</p>}
      </div>
      {children}
    </header>
  );
};

export const Content = Object.assign(ContentRoot, {
  Title: ContentTitle,
  Root: ContentRoot,
});

export default Content;
