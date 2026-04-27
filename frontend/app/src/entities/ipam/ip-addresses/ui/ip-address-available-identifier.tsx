import { ArrowRightIcon, PlusIcon } from "lucide-react";

import { Button, type ButtonProps } from "@/shared/components/aria/button";
import { classNames } from "@/shared/utils/common";

import type { IpAddressAvailableNode } from "@/entities/ipam/ip-addresses/domain/types";

export interface IPAddressAvailableIdentifierProps extends ButtonProps {
  ipAddressAvailableNode: IpAddressAvailableNode;
}

export function IpAddressAvailableIdentifier({
  ipAddressAvailableNode,
  className,
  ...props
}: IPAddressAvailableIdentifierProps) {
  const firstAddressAvailable = ipAddressAvailableNode.address.value;
  const lastAddressAvailable = ipAddressAvailableNode.last_address.value;

  return firstAddressAvailable === lastAddressAvailable ? (
    <Button
      variant="ghost"
      size="sm"
      className={classNames(
        "rounded-full pr-2.5 pl-1.5 text-neutral-400 data-hovered:underline",
        className
      )}
      {...props}
    >
      <PlusIcon className="mr-1 size-4" />
      <span>{firstAddressAvailable}</span>
    </Button>
  ) : (
    <Button
      variant="ghost"
      size="sm"
      className={classNames(
        "rounded-full pr-2.5 pl-1.5 text-neutral-400 data-hovered:underline",
        className
      )}
      {...props}
    >
      <PlusIcon className="mr-1 size-4" />
      <span>{firstAddressAvailable}</span>
      <ArrowRightIcon className="size-3.5" />
      <span>{lastAddressAvailable}</span>
    </Button>
  );
}
