import { HTMLAttributes, ReactNode } from "react";
import { classNames } from "../../utils/common";
import { Retry } from "../../components/buttons/retry";

const ContentRoot = ({ className, ...props }: HTMLAttributes<HTMLElement>) => {
  return <main className={classNames("h-full overflow-auto", className)} {...props} />;
};

type ContentTitleProps = {
  children?: ReactNode;
  title?: ReactNode;
  description?: ReactNode;
  reload?: () => void;
  isReloadLoading?: boolean;
};

export const ContentTitle = ({
  children,
  description,
  isReloadLoading,
  reload,
  title,
}: ContentTitleProps) => {
  return (
    <header className="h-16 bg-custom-white flex items-center px-4 border-b">
      <div className="flex flex-col overflow-hidden pr-2">
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
