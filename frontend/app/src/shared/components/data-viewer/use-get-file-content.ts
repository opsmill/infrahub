import { useQuery } from "@tanstack/react-query";

async function fetchFileContent(url: string): Promise<string> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch file: ${response.status} ${response.statusText}`);
  }
  return response.text();
}

export function useGetFileContent(url: string | null) {
  return useQuery({
    queryKey: ["file-content", url],
    queryFn: () => fetchFileContent(url!),
    enabled: !!url,
  });
}
