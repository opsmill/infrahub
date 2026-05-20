import {
  type GetFileContentDiffFromApiParams,
  getFileContentDiffFromApi,
} from "@/entities/diff/api/get-file-content-diff-from-api";

export type GetFileContentDiffParams = GetFileContentDiffFromApiParams;

export interface FileThread {
  id: string;
  display_label?: string | null;
  resolved?: { value?: boolean | null } | null;
  file?: { value?: string | null } | null;
  commit?: { value?: string | null } | null;
  repository?: { node?: { id?: string | null } | null } | null;
  line_number?: { value?: number | null } | null;
  comments?: {
    edges?: Array<{
      node_metadata?: {
        created_at?: string | null;
        created_by?: { display_label?: string | null } | null;
      } | null;
      node?: { id?: string | null; text?: { value?: string | null } | null } | null;
    } | null> | null;
  } | null;
}

export interface FileContentDiff {
  threads: FileThread[];
}

export async function getFileContentDiff(
  params: GetFileContentDiffParams
): Promise<FileContentDiff> {
  const { data, errors } = await getFileContentDiffFromApi(params);

  if (errors?.length) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const threads =
    (data?.CoreFileThread?.edges?.map((edge) => edge?.node).filter(Boolean) as FileThread[]) ?? [];

  return { threads };
}
