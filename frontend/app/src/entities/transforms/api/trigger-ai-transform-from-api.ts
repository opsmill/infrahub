import { INFRAHUB_API_SERVER_URL } from "@/shared/config/config";

import { ACCESS_TOKEN_KEY } from "@/entities/authentication/constants";

export interface TriggerAITransformFromApiParams {
  transformId: string;
  branchName: string;
}

export async function triggerAITransformFromApi({
  transformId,
  branchName,
}: TriggerAITransformFromApiParams): Promise<void> {
  const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);

  const response = await fetch(
    `${INFRAHUB_API_SERVER_URL}/api/transform/ai/${encodeURIComponent(transformId)}/trigger?branch=${encodeURIComponent(branchName)}`,
    {
      method: "POST",
      headers: {
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
    }
  );

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to trigger AI transform: ${text}`);
  }
}
