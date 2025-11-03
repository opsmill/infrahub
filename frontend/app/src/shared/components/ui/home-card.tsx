import type React from "react";

import { classNames } from "@/shared/utils/common";

interface HomeCardProps {
  className?: string;
  children?: React.ReactNode;
}

const HomeCardRoot = ({ className, children }: HomeCardProps) => {
  return (
    <div className={classNames("rounded-lg border border-gray-200 bg-white", className)}>
      {children}
    </div>
  );
};

const HomeCardTitle = ({ className, ...props }: HomeCardProps) => {
  return (
    <header
      className={classNames("rounded-t border-gray-200 border-b p-3 font-bold", className)}
      {...props}
    />
  );
};

const HomeCardContent = ({ className, ...props }: HomeCardProps) => {
  return <header className={classNames("p-3", className)} {...props} />;
};

export const HomeCard = Object.assign(HomeCardRoot, {
  Title: HomeCardTitle,
  Content: HomeCardContent,
});
