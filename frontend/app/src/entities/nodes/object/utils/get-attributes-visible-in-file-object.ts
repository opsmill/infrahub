import type { AttributeSchema } from "@/entities/schema/types";

const FILE_OBJECT_HIDDEN_ATTRIBUTES = [
  "file_name",
  "file_size",
  "file_type",
  "storage_id",
  "checksum",
];

export function getAttributesVisibleInFileObject(attributes: AttributeSchema[]): AttributeSchema[] {
  return attributes.filter((attr) => !FILE_OBJECT_HIDDEN_ATTRIBUTES.includes(attr.name));
}
