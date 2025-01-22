import { fetchStream } from "@/shared/api/rest/fetch";
import NoDataFound from "@/shared/components/errors/no-data-found";
import LoadingScreen from "@/shared/components/loading-screen";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { useCallback, useEffect, useState } from "react";
import { toast } from "react-toastify";
import { Download } from "./buttons/download";
import { Svg } from "./display/svg";
import { JsonEditor } from "./editor/json/json-editor";
import { MarkdownEditor } from "./editor/markdown";
import { TextEditor } from "./editor/text/text-editor";
import { YamlEditor } from "./editor/yaml/yaml-editor";

type tFile = {
  url: string;
  contentType?: string;
};

export const File = ({ url, contentType }: tFile) => {
  const [isLoading, setIsLoading] = useState(false);
  const [fileContent, setFileContent] = useState("");

  const fetchFileDetails = useCallback(async () => {
    if (!url) return;

    setIsLoading(true);

    try {
      const fileResult = await fetchStream(url);

      setFileContent(fileResult);
    } catch (err) {
      console.error("err: ", err);
      toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading file content" />);
    }

    setIsLoading(false);
  }, []);

  useEffect(() => {
    fetchFileDetails();
  }, []);

  if (isLoading) {
    return <LoadingScreen />;
  }

  if (!fileContent) {
    return <NoDataFound message="No file found." />;
  }

  if (contentType === "application/json") {
    return (
      <div className="p-4">
        <JsonEditor value={fileContent} disabled onChange={function (): void {}} />

        <Download
          value={JSON.parse(fileContent)}
          download={"file.json"}
          className="absolute right-6 top-6"
          variant={"outline"}
        />
      </div>
    );
  }

  if (contentType === "application/markdown") {
    return (
      <div className="p-4">
        <MarkdownEditor value={fileContent} />

        <Download
          value={fileContent}
          download={"markdown.md"}
          className="absolute right-6 top-6"
          variant={"outline"}
        />
      </div>
    );
  }

  if (contentType === "application/yaml") {
    return (
      <div className="p-4 relative">
        <YamlEditor value={fileContent} disabled onChange={function (): void {}} />

        <Download
          value={fileContent}
          download={"file.yaml"}
          className="absolute right-6 top-6"
          variant={"outline"}
        />
      </div>
    );
  }

  if (contentType === "image/svg+xml") {
    return (
      <div className="p-4 relative">
        <Svg value={fileContent} className="border rounded-md p-2" />

        <Download
          value={fileContent}
          download={"file.svg"}
          className="absolute right-6 top-6"
          variant={"outline"}
        />
      </div>
    );
  }

  return (
    <div className="p-4 relative">
      <TextEditor value={fileContent} disabled onChange={function (): void {}} />

      <Download
        value={fileContent}
        download={"file.txt"}
        className="absolute right-6 top-6"
        variant={"outline"}
      />
    </div>
  );
};
