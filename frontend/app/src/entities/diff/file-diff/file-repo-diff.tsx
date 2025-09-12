import Accordion from "@/shared/components/display/accordion";
import "react-diff-view/style/index.css";

import { FileContentDiff } from "./file-content-diff";

export const FileRepoDiff = (props: any) => {
  const { diff } = props;

  const { files } = diff;

  return (
    <div className={"m-4 rounded-lg bg-white p-2 shadow-sm"}>
      <Accordion title={diff.display_name}>
        {files.map((file: any, index: number) => (
          <FileContentDiff
            key={index}
            repositoryId={diff.id}
            repositoryDisplayName={diff.display_name}
            file={file}
            commitFrom={diff.commmit_from}
            commitTo={diff.commit_to}
          />
        ))}
      </Accordion>
    </div>
  );
};
