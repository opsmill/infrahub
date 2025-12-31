import type { NodeCore, NodeRelationshipMetadata } from "@/entities/nodes/types";

export interface FileNodeData extends NodeCore {
  name?: { value: string };
  file_name?: { value: string };
  file_size?: { value: number };
  content_type?: { value: string };
  storage_id?: { value: string };
}

export interface FileRelationshipOneData {
  node: FileNodeData | null;
  properties: NodeRelationshipMetadata;
}

export interface FileRelationshipManyData {
  edges: Array<FileRelationshipOneData>;
}

export type FileRelationshipData = FileRelationshipOneData | FileRelationshipManyData;
