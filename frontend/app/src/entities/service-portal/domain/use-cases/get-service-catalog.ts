import { getServiceCatalogFromApi } from "@/entities/service-portal/api/get-service-catalog-from-api";
import type { ServiceCatalogEntry } from "@/entities/service-portal/domain/model/service-catalog";

export type GetServiceCatalogResult = Array<ServiceCatalogEntry>;

export const getServiceCatalog = async (): Promise<GetServiceCatalogResult> => {
  const { data } = await getServiceCatalogFromApi();

  return data.ServiceCatalog.entries.map((entry) => ({
    id: entry.id,
    name: entry.name,
    description: entry.description ?? null,
    icon: entry.icon ?? null,
    tags: entry.tags,
    targetKind: entry.target_kind,
    mode: entry.mode,
    fields: entry.fields,
    generators: entry.generators,
    templateId: entry.template_id ?? null,
  }));
};
