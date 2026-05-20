import {
  type GetDiffCommentsFromApiParams,
  getDiffCommentsFromApi,
} from "@/entities/diff/api/get-diff-comments-from-api";

export type GetDiffCommentsParams = GetDiffCommentsFromApiParams;

export interface DiffThread {
  id: string;
  display_label?: string | null;
  resolved?: { value?: boolean | null } | null;
  comments?: {
    count?: number | null;
    edges?: Array<{
      node_metadata?: {
        created_at?: string | null;
        created_by?: { display_label?: string | null } | null;
      } | null;
      node?: {
        id?: string | null;
        display_label?: string | null;
        text?: { value?: string | null } | null;
      } | null;
    } | null> | null;
  } | null;
}

export interface DiffComments {
  thread: DiffThread | null;
}

export async function getDiffComments(params: GetDiffCommentsParams): Promise<DiffComments> {
  const { data, errors } = await getDiffCommentsFromApi(params);

  if (errors?.length) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const thread = data?.CoreObjectThread?.edges?.[0]?.node ?? null;

  return { thread: thread as DiffThread | null };
}
