import type { IpPoolResource } from "@/entities/resource-manager/domain/model/ip-pool";

const weightOf = (resource: IpPoolResource) => resource.allocationWeight ?? 0;

// mirrors the server's weight order, which applies only when every resource prefix kind has a weight; otherwise all weights are null and prefix order decides
export const sortIpPoolResourcesByFillOrder = (resources: IpPoolResource[]): IpPoolResource[] =>
  [...resources].sort(
    (a, b) =>
      weightOf(b) - weightOf(a) ||
      a.display_label.localeCompare(b.display_label, undefined, { numeric: true })
  );
