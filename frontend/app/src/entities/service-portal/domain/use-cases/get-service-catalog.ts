import { getServiceCatalogFromApi } from "@/entities/service-portal/api/get-service-catalog-from-api";
import type { ServiceCatalogEntry } from "@/entities/service-portal/domain/model/service-catalog";

export type GetServiceCatalogResult = Array<ServiceCatalogEntry>;

export const getServiceCatalog = async (): Promise<GetServiceCatalogResult> => {
  const { data } = await getServiceCatalogFromApi();

  return data.ServiceCatalog.entries.map((entry) => ({
    ...entry,
    description: entry.description ?? null,
    icon: entry.icon ?? null,
    template_id: entry.template_id ?? null,
  }));
};
