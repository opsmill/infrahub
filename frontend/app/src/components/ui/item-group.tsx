import React from "react";
import { classNames } from "@/utils/common";

interface ItemGroupProps extends React.HTMLAttributes<HTMLUListElement> {}

export default function ItemGroup({ className, ...props }: ItemGroupProps) {
  return <ul className={classNames("divide-y", className)} {...props} />;
}
