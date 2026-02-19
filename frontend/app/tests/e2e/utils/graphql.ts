import { type APIRequestContext, expect } from "@playwright/test";

const API_URL = process.env.CI ? process.env.INFRAHUB_ADDRESS : "http://localhost:8000";
const API_KEY = "06438eb2-8019-4776-878c-0941b1f1d1ec";

interface GraphQLResponse<T = any> {
  data?: T;
  errors?: Array<{ message: string }>;
}

async function executeGraphQLMutation<T>(
  request: APIRequestContext,
  query: string,
  variables: Record<string, any>
): Promise<T> {
  const response = await request.post(`${API_URL}/graphql`, {
    headers: { "X-INFRAHUB-KEY": API_KEY },
    data: { query, variables },
  });

  expect(response.ok()).toBeTruthy();
  const result: GraphQLResponse<T> = await response.json();

  if (result.errors) {
    result.errors.forEach((error) => {
      console.error(error.message);
    });
    throw new Error(`GraphQL Error: ${result.errors[0]?.message}`);
  }

  return result.data as T;
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
