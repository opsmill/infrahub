import type { IpPoolResource } from "@/entities/resource-manager/domain/model/ip-pool";

const weightOf = (resource: IpPoolResource) => resource.allocationWeight ?? 0;

// the pool allocates from the heaviest resource prefix first; ties keep a readable prefix order
export const sortIpPoolResourcesByFillOrder = (resources: IpPoolResource[]): IpPoolResource[] =>
  [...resources].sort(
    (a, b) =>
      weightOf(b) - weightOf(a) ||
      a.display_label.localeCompare(b.display_label, undefined, { numeric: true })
  );
