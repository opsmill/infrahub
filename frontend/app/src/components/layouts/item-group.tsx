import { classNames } from "@/utils/common";
import React from "react";

interface ItemGroupProps extends React.HTMLAttributes<HTMLUListElement> {}

export default function ItemGroup({ className, ...props }: ItemGroupProps) {
  return <ul className={classNames("space-y-4", className)} {...props} />;
}
