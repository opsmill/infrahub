import { useRequiredParams } from "@/shared/hooks/use-required-params";

import { ServiceOrder } from "@/entities/service-portal/ui/service-order";

export function Component() {
  const { entryId } = useRequiredParams("entryId");
  return <ServiceOrder entryId={entryId} />;
}
