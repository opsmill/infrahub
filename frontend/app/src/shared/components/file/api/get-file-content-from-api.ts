export interface GetFileContentFromApiParams {
  url: string;
}

export async function getFileContentFromApi({
  url,
}: GetFileContentFromApiParams): Promise<string | null> {
  try {
    const response = await fetch(url);

    if (!response.ok) {
      return null;
    }

    return await response.text();
  } catch {
    return null;
  }
}
