import {
  type GetArtifactContentDiffFromApiParams,
  getArtifactContentDiffFromApi,
} from "@/entities/diff/api/get-artifact-content-diff-from-api";

export type GetArtifactContentDiffParams = GetArtifactContentDiffFromApiParams;

export interface ArtifactThread {
  id: string;
  display_label?: string | null;
  line_number?: { value?: number | null } | null;
  storage_id?: { value?: string | null } | null;
  resolved?: { value?: boolean | null } | null;
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

export interface ArtifactContentDiff {
  threads: ArtifactThread[];
}

export async function getArtifactContentDiff(
  params: GetArtifactContentDiffParams
): Promise<ArtifactContentDiff> {
  const { data, errors } = await getArtifactContentDiffFromApi(params);

  if (errors?.length) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const threads =
    (data?.CoreArtifactThread?.edges
      ?.map((edge) => edge?.node)
      .filter(Boolean) as ArtifactThread[]) ?? [];

  return { threads };
}
