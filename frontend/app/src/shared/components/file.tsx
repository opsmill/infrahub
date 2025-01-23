import { fetchStream } from "@/shared/api/rest/fetch";
import NoDataFound from "@/shared/components/errors/no-data-found";
import LoadingScreen from "@/shared/components/loading-screen";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { useCallback, useEffect, useState } from "react";
import { toast } from "react-toastify";
import { Download } from "./buttons/download";
import { Svg } from "./display/svg";
import { CodeViewer } from "./editor/code/code-viewer";
import { MarkdownEditor } from "./editor/markdown";
import { Badge } from "./ui/badge";

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
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Download value={JSON.parse(fileContent)} download={"file.json"} variant={"outline"} />
          <Badge>Application / JSON</Badge>
        </div>

        <CodeViewer>{fileContent}</CodeViewer>
      </div>
    );
  }

  if (contentType === "text/markdown") {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Download value={fileContent} download={"markdown.md"} variant={"outline"} />
          <Badge>Text / Markdown</Badge>
        </div>

        <MarkdownEditor value={fileContent} />
      </div>
    );
  }

  if (contentType === "application/yaml") {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Download value={fileContent} download={"file.yaml"} variant={"outline"} />
          <Badge>Application / YAML</Badge>
        </div>

        <CodeViewer language="yaml">{fileContent}</CodeViewer>
      </div>
    );
  }

  if (contentType === "image/svg+xml") {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Download value={fileContent} download={"file.svg"} variant={"outline"} />
          <Badge>Image / SVG</Badge>
        </div>

        <Svg value={fileContent} className="border rounded-md p-2" />
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Download value={fileContent} download={"file.txt"} variant={"outline"} />
        <Badge>Plain / Text</Badge>
      </div>

      <CodeViewer language="text">{fileContent}</CodeViewer>
    </div>
  );
};
