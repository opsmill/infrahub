import { type APIRequestContext, expect } from "@playwright/test";

import { ERROR_CODES, parseCatalogueError } from "../../../src/shared/api/errors";

const API_URL = process.env.CI ? process.env.INFRAHUB_ADDRESS : "http://localhost:8000";
const API_KEY = "06438eb2-8019-4776-878c-0941b1f1d1ec";

// A merging branch blocks writes to the default branch. Retry until blocking merge is complete or time is up
const MERGE_RETRY_TIMEOUT_MS = 120_000;
const MERGE_RETRY_DELAY_MS = 2000;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

interface GraphQLResponse<T = any> {
  data?: T;
  errors?: Array<{ message: string; extensions?: unknown }>;
}

async function executeGraphQLMutation<T>(
  request: APIRequestContext,
  query: string,
  variables: Record<string, any>
): Promise<T> {
  const deadline = Date.now() + MERGE_RETRY_TIMEOUT_MS;

  for (;;) {
    const response = await request.post(`${API_URL}/graphql`, {
      headers: { "X-INFRAHUB-KEY": API_KEY },
      data: { query, variables },
    });

    expect(response.ok()).toBeTruthy();
    const result: GraphQLResponse<T> = await response.json();

    if (!result.errors) {
      return result.data as T;
    }

    const isMergeInProgress = result.errors.some(
      (error) => parseCatalogueError(error.extensions).code === ERROR_CODES.MERGE_IN_PROGRESS
    );
    if (isMergeInProgress && Date.now() < deadline) {
      await sleep(MERGE_RETRY_DELAY_MS);
      continue;
    }

    result.errors.forEach((error) => {
      console.error(error.message);
    });
    throw new Error(`GraphQL Error: ${result.errors[0]?.message}`);
  }
}

export const createBranchAPI = async (request: APIRequestContext, name: string) => {
  const mutation = `
    mutation BranchCreate($name: String!, $description: String, $sync_with_git: Boolean) {
      BranchCreate(data: { name: $name, description: $description, sync_with_git: $sync_with_git }) {
        object {
          id
          name
          description
          origin_branch
          branched_from
          created_at
          sync_with_git
          is_default
        }
      }
    }
  `;

  return await executeGraphQLMutation(request, mutation, { name });
};

export const mergeBranchAPI = async (request: APIRequestContext, name: string): Promise<any> => {
  const mutation = `
    mutation BranchMerge($name: String!) {
      BranchMerge(data: { name: $name }) {
        ok
        object {
          id
          name
        }
      }
    }
  `;

  return await executeGraphQLMutation(request, mutation, { name });
};

export const deleteBranchAPI = async (request: APIRequestContext, name: string): Promise<any> => {
  const mutation = `
    mutation BranchDelete($name: String!) {
      BranchDelete(data: { name: $name }) {
        ok
      }
    }
  `;

  return await executeGraphQLMutation(request, mutation, { name });
};
