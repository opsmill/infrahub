import { useQuery } from "@tanstack/react-query";

async function fetchFileContent(url: string): Promise<string | null> {
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

export function useGetFileContent(url: string | null) {
  return useQuery({
    queryKey: ["file-content", url],
    queryFn: () => fetchFileContent(url!),
    enabled: !!url,
  });
}
