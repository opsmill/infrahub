import { Card, CardContent, CardHeader } from "@infrahub/ui";
import type React from "react";
import { Link, type LinkProps } from "react-router";

import { classNames } from "@/shared/utils/common";

interface HomeCardProps {
  className?: string;
  children?: React.ReactNode;
}

const HomeCardTitle = ({ className, ...props }: HomeCardProps) => {
  return (
    <CardHeader
      className={classNames(
        "flex items-center justify-between from-white font-semibold",
        className
      )}
      {...props}
    />
  );
};

const HomeCardLink = ({ className, ...props }: LinkProps) => {
  return (
    <Link
      className={classNames(
        "flex items-center font-normal text-neutral-500 text-sm hover:underline",
        className
      )}
      {...props}
    />
  );
};

export const HomeCard = Object.assign(Card, {
  Title: HomeCardTitle,
  Link: HomeCardLink,
  Content: CardContent,
});
