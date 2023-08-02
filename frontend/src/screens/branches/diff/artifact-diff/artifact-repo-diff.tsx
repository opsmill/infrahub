import "react-diff-view/style/index.css";
import Accordion from "../../../../components/accordion";
import { ArtifactContentDiff } from "./artifact-content-diff";

export const ArtifactRepoDiff = (props: any) => {
  const { diff } = props;

  return (
    <div className={"rounded-lg shadow p-2 m-4 bg-custom-white"}>
      <Accordion title={diff.display_label}>
        <ArtifactContentDiff itemNew={diff.item_new} itemPrevious={diff.item_previous} />
      </Accordion>
    </div>
  );
};
