import "react-diff-view/style/index.css";
import Accordion from "../../../components/display/accordion";
import { FileContentDiff } from "./file-content-diff";

export const FileRepoDiff = (props: any) => {
  const { diff } = props;

  const { files } = diff;

  return (
    <div className={"rounded-lg shadow p-2 m-4 bg-custom-white"}>
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
