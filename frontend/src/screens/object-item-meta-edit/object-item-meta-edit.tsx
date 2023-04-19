import { iNodeSchema } from "../../state/atoms/schema.atom";
import { getFormStructureForMetaEdit } from "../../utils/formStructureForCreateEdit";
import updateObjectWithId from "../../utils/updateObjectWithId";
import EditFormHookComponent from "../edit-form-hook/edit-form-hook-component";

// const optionsLeft: SelectOption[] = [
//   {
//     label: "Account",
//     value: "account"
//   },
//   {
//     label: "Group",
//     value: "group"
//   },
//   {
//     label: "Repository",
//     value: "repository"
//   }
// ];

// function Toggle(props: {label: string}) {
//   const { label } = props;
//   const [enabled, setEnabled] = useState(false);

//   return (
//     <Switch.Group as="div" className="flex flex-col justify-center">
//       <Switch.Label as="span" className="text-sm">
//         <span className="font-medium text-gray-900">{label}</span>
//       </Switch.Label>
//       <Switch
//         checked={enabled}
//         onChange={setEnabled}
//         className={classNames(
//           enabled ? "bg-indigo-600" : "bg-gray-200",
//           "relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:ring-offset-2 mt-2"
//         )}
//       >
//         <span
//           aria-hidden="true"
//           className={classNames(
//             enabled ? "translate-x-5" : "translate-x-0",
//             "pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out"
//           )}
//         />
//       </Switch>
//     </Switch.Group>
//   );
// }

interface Props {
  row: any;
  schema: iNodeSchema;
  type: "attribute" | "relationship",
  attributeOrRelationshipName: any;
  schemaList: iNodeSchema[];
  closeDrawer: Function;
  onUpdateComplete: Function;
}

export default function ObjectItemMetaEdit(props: Props) {
  const { row, type, attributeOrRelationshipName, schema, schemaList } = props;
  const formStructure = getFormStructureForMetaEdit(row, type, attributeOrRelationshipName, schemaList);

  async function onSubmit(data: any, error: any) {
    data[attributeOrRelationshipName].id = props.row[attributeOrRelationshipName].id;
    if (Object.keys(data).length) {
      try {
        await updateObjectWithId(row.id!, schema, data);
      } catch {
        console.error("Something went wrong while updating the object");
      }
      props.onUpdateComplete();
    } else {
      console.info("Nothing to update");
      props.onUpdateComplete();
    }
  }

  return (
    <div className="flex-1 bg-white flex">
      <EditFormHookComponent onCancel={props.closeDrawer} onSubmit={onSubmit} fields={formStructure} />
    </div>
  );
  // return (
  //   <>
  //     <div className="mt-2 bg-white px-4 flex-1">
  //       <div>
  //         <Select2Step
  //           defaultValue={{ parent: "group", child: "0831f2dd-4138-4b00-9fdc-c366abee2bd0" }}
  //           label="Source"
  //           optionsLeft={optionsLeft}
  //           onChange={(value) => {
  //             // console.log(value);
  //           }}
  //         />
  //       </div>
  //       <div>
  //         <Select2Step
  //           defaultValue={{ parent: "group", child: "0831f2dd-4138-4b00-9fdc-c366abee2bd0" }}
  //           label="Owner"
  //           optionsLeft={optionsLeft}
  //           onChange={(value) => {
  //             // console.log(value);
  //           }}
  //         />
  //       </div>
  //       <div className="mt-4">
  //         <Toggle label="Is Visible" />
  //       </div>
  //       <div className="mt-4">
  //         <Toggle label="Is Protected" />
  //       </div>
  //     </div>
  //     <div className="mt-6 flex items-center justify-end gap-x-6 py-3 max-w-lg pr-3 border-t">
  //       <button type="button" className="rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50">
  //         Cancel
  //       </button>
  //       <button
  //         type="submit"
  //         className="rounded-md bg-indigo-600 py-2 px-3 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
  //       >
  //         Save
  //       </button>
  //     </div>
  //   </>
  // );
}
