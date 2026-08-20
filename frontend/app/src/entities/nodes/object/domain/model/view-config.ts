import type { RelationshipKind } from "@/entities/nodes/object/domain/model/node";

export const attributesKindForDetailsViewExclude = ["HashedPassword"];

export const relationshipsForListView = {
  one: ["Attribute", "Hierarchy", "Parent"],
  many: ["Attribute"],
};

export const relationshipsForDetailsView: { one: RelationshipKind[]; many: RelationshipKind[] } = {
  one: ["Generic", "Attribute", "Component", "Parent", "Hierarchy"],
  many: ["Attribute", "Parent"],
};

export const relationshipKindForForm: Array<RelationshipKind> = ["Attribute", "Parent"];
