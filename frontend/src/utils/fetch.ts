
export const fetchUrl = async (url: string, payload?: RequestInit) => {
  const rawResponse = await fetch(url, payload);
  return rawResponse?.json();
};