import { HTMLAttributes, ReactNode } from "react";
import { classNames } from "../../utils/common";
import { Retry } from "../../components/buttons/retry";

const ContentRoot = ({ className, ...props }: HTMLAttributes<HTMLElement>) => {
  return <main className={classNames("h-full overflow-auto", className)} {...props} />;
};

type ContentTitleProps = {
  children?: ReactNode;
  title?: ReactNode;
  description?: string;
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
    <header className="bg-custom-white h-16 flex items-center px-4">
      {title && (
        <h1 className="text-md font-semibold text-gray-900 mr-2 flex items-center gap-2">
          {title}
        </h1>
      )}
      {description && <p className="text-sm">{description}</p>}
      {reload && <Retry isLoading={isReloadLoading} onClick={reload} />}
      {children}
    </header>
  );
};

export const Content = Object.assign(ContentRoot, {
  Title: ContentTitle,
  Root: ContentRoot,
});

export default Content;
