import {
  type GetDiffThreadFromApiParams,
  getDiffThreadFromApi,
} from "@/entities/diff/api/get-diff-thread-from-api";

export type GetDiffThreadParams = GetDiffThreadFromApiParams;

export interface DiffThreadNode {
  id: string;
  comments?: { count?: number | null } | null;
}

export interface DiffThreadPermissions {
  edges?: Array<{
    node?: {
      kind?: string | null;
      view?: boolean | null;
      create?: boolean | null;
      update?: boolean | null;
      delete?: boolean | null;
    } | null;
  } | null> | null;
}

export interface DiffThreadData {
  thread: DiffThreadNode | null;
  permissions: DiffThreadPermissions | null;
}

export async function getDiffThread(params: GetDiffThreadParams): Promise<DiffThreadData> {
  const { data, errors } = await getDiffThreadFromApi(params);

  if (errors?.length) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  const thread = data?.CoreObjectThread?.edges?.[0]?.node ?? null;
  const permissions = data?.CoreObjectThread?.permissions ?? null;

  return {
    thread: thread as DiffThreadNode | null,
    permissions: permissions as DiffThreadPermissions | null,
  };
}
