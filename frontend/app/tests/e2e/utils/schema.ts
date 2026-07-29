import type { APIRequestContext } from "@playwright/test";

const API_URL = process.env.CI ? process.env.INFRAHUB_ADDRESS : "http://localhost:8000";
const API_KEY = "06438eb2-8019-4776-878c-0941b1f1d1ec";

// Loading a schema runs migrations and constraint validation, so it takes far longer than a
// regular API call.
const SCHEMA_LOAD_TIMEOUT_MS = 5 * 60 * 1000;

/**
 * Load a schema onto a branch through the schema API.
 *
 * Use it when a test needs a node kind the demo dataset does not ship. Always target a
 * test-owned branch so the default branch keeps the shape every other test relies on.
 */
export const loadSchemaAPI = async (
  request: APIRequestContext,
  branch: string,
  schema: Record<string, unknown>
) => {
  const response = await request.post(
    `${API_URL}/api/schema/load?branch=${encodeURIComponent(branch)}`,
    {
      headers: { "X-INFRAHUB-KEY": API_KEY },
      data: { schemas: [schema] },
      timeout: SCHEMA_LOAD_TIMEOUT_MS,
    }
  );

  if (!response.ok()) {
    throw new Error(`Schema load failed (${response.status()}): ${await response.text()}`);
  }

  return response.json();
};
