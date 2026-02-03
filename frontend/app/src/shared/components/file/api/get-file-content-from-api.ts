const read = async (reader: ReadableStreamDefaultReader<Uint8Array>): Promise<string> => {
  const result = await reader.read();
  const currentValue = new TextDecoder().decode(result.value);

  if (result.done) {
    return currentValue;
  }

  const nextResult = await read(reader);
  return `${currentValue}${nextResult}`;
};

export interface GetFileContentFromApiParams {
  url: string;
}

export async function getFileContentFromApi({
  url,
}: GetFileContentFromApiParams): Promise<string | null> {
  let reader: ReadableStreamDefaultReader<Uint8Array> | null = null;

  try {
    const response = await fetch(url);

    if (!response.ok) {
      return null;
    }

    const stream = response.body;
    if (!stream) {
      return null;
    }

    reader = stream.getReader();
    return await read(reader);
  } catch {
    return null;
  } finally {
    if (reader) {
      reader.releaseLock();
    }
  }
}
