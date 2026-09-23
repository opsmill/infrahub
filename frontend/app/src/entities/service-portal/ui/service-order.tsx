import { Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { LinkTab } from "@/shared/components/ui/link";

import { useGetServiceCatalog } from "@/entities/service-portal/ui/queries/get-service-catalog.query";
import { getServiceEntryUrl } from "@/entities/service-portal/ui/routing/service-portal-urls";
import { ServiceEntryIcon } from "@/entities/service-portal/ui/service-entry-icon";
import { ServiceOrderForm } from "@/entities/service-portal/ui/service-order-form";

export function ServiceOrder({ entryId }: { entryId: string }) {
  const { data: entries, isPending, error } = useGetServiceCatalog();

  if (isPending) return <LoadingIndicator className="my-8" />;
  if (error) return <ErrorScreen message={error.message} />;

  const entry = entries.find(({ id }) => id === entryId);
  if (!entry) {
    return <NoDataFound message="This service is no longer available in the catalog." />;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <ServiceEntryIcon icon={entry.icon} className="size-10 text-2xl" />
        <div>
          <h1 className="font-semibold text-lg">{entry.name}</h1>
          {entry.description && <p className="text-neutral-600 text-sm">{entry.description}</p>}
        </div>
      </div>

      <nav aria-label="Tabs">
        <Row className="border-gray-200 border-b">
          <LinkTab to={getServiceEntryUrl(entry.id)}>New</LinkTab>
        </Row>
      </nav>

      <ServiceOrderForm entry={entry} />
    </div>
  );
}
