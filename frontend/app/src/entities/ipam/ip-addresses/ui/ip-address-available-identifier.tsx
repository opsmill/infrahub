import { IpAddressAvailableNode } from "@/entities/ipam/ip-addresses/domain/types";
import { Button, ButtonProps } from "@/shared/components/buttons/button-primitive";
import { classNames } from "@/shared/utils/common";
import { ArrowRightIcon, PlusIcon } from "lucide-react";

export interface IPAddressRangeAvailableIdentifierProps extends ButtonProps {
  ipAddressAvailableNode: IpAddressAvailableNode;
}

export function IpAddressAvailableIdentifier({
  ipAddressAvailableNode,
  className,
  ...props
}: IPAddressRangeAvailableIdentifierProps) {
  const firstAddressAvailable = ipAddressAvailableNode.address.value;
  const lastAddressAvailable = ipAddressAvailableNode.last_address.value;

  return firstAddressAvailable === lastAddressAvailable ? (
    <Button
      variant="ghost"
      size="sm"
      className={classNames(
        "rounded-full hover:underline hover:bg-gray-400/10 gap-3.75 pl-1.5 pr-2.5",
        className
      )}
      {...props}
    >
      <PlusIcon className="size-4 mr-px" />
      <span>{firstAddressAvailable}</span>
    </Button>
  ) : (
    <Button
      variant="ghost"
      size="sm"
      className={classNames("rounded-full hover:underline hover:bg-gray-400/10 gap-1", className)}
      {...props}
    >
      <PlusIcon className="size-4 mr-3" />
      <span>{firstAddressAvailable}</span>
      <ArrowRightIcon className="size-3.5" />
      <span>{lastAddressAvailable}</span>
    </Button>
  );
}
