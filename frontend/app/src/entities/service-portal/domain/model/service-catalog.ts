export interface ServiceCatalogEntry {
  id: string;
  name: string;
  description: string | null;
  // An `mdi:` icon name
  icon: string | null;
  tags: string[];
  target_kind: string;
  mode: string;
  // Attribute and relationship names of the target kind shown on the order form, in form order
  fields: string[];
  generators: string[];
  template_id: string | null;
}
