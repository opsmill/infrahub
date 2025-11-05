import type React from "react";
import { Link, type LinkProps } from "react-router";

import { classNames } from "@/shared/utils/common";

import { Card } from "./card";

interface HomeCardProps {
  className?: string;
  children?: React.ReactNode;
}

const HomeCardRoot = ({ className, ...props }: HomeCardProps) => {
  return <Card className={classNames("p-0", className)} {...props} />;
};

const HomeCardTitle = ({ className, ...props }: HomeCardProps) => {
  return (
    <header
      className={classNames("rounded-t border-gray-200 border-b p-3 font-bold", className)}
      {...props}
    />
  );
};

const HomeCardLink = ({ className, ...props }: LinkProps) => {
  return (
    <Link
      className={classNames(
        "flex items-center font-normal text-gray-500 text-sm hover:underline",
        className
      )}
      {...props}
    />
  );
};

const HomeCardContent = ({ className, ...props }: HomeCardProps) => {
  return <div className={classNames("p-3", className)} {...props} />;
};

export const HomeCard = Object.assign(HomeCardRoot, {
  Title: HomeCardTitle,
  Link: HomeCardLink,
  Content: HomeCardContent,
});
