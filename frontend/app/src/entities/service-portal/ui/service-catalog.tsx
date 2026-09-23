import { Card, CardContent } from "@infrahub/ui";
import { Link } from "react-router";

import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Badge } from "@/shared/components/ui/badge";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import type { ServiceCatalogEntry } from "@/entities/service-portal/domain/model/service-catalog";
import { useGetServiceCatalog } from "@/entities/service-portal/ui/queries/get-service-catalog.query";
import { getServiceEntryUrl } from "@/entities/service-portal/ui/routing/service-portal-urls";
import { ServiceEntryIcon } from "@/entities/service-portal/ui/service-entry-icon";

export function ServiceCatalog() {
  const { data: entries, isPending, error } = useGetServiceCatalog();

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-semibold text-lg">Service catalog</h1>
        <p className="text-neutral-600 text-sm">
          Pick the service you need and fill in a short form.
        </p>
      </div>

      {isPending && <LoadingIndicator className="my-8" />}

      {error && <ErrorScreen message={error.message} />}

      {entries?.length === 0 && (
        <NoDataFound message="No services are available yet. Check back later or ask your administrator." />
      )}

      {!!entries?.length && (
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {entries.map((entry) => (
            <li key={entry.id}>
              <ServiceCatalogCard entry={entry} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ServiceCatalogCard({ entry }: { entry: ServiceCatalogEntry }) {
  return (
    <Link
      to={getServiceEntryUrl(entry.id)}
      className={classNames(focusVisibleStyle, "block h-full rounded-2xl")}
    >
      <Card className="h-full transition-colors hover:border-custom-blue-600/50">
        <CardContent className="flex h-full flex-col gap-2">
          <div className="flex items-center gap-2">
            <ServiceEntryIcon icon={entry.icon} className="size-9 text-xl" />
            <h2 className="font-medium text-neutral-800">{entry.name}</h2>
          </div>

          {entry.description && <p className="text-neutral-600 text-sm">{entry.description}</p>}

          {entry.tags.length > 0 && (
            <div className="mt-auto flex flex-wrap gap-1">
              {entry.tags.map((tag) => (
                <Badge key={tag}>{tag}</Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}
