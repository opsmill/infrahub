import { Avatar } from "@/components/display/avatar";
import { Tooltip } from "@/components/ui/tooltip";

interface GroupMembersProps {
  members: Array<string>;
}

export function GroupMembers({ members }: GroupMembersProps) {
  const trimedMembers = members.slice(0, 5);

  const lengthDiff = members.length - trimedMembers.length;

  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center relative w-32 h-12">
        {trimedMembers.map((member, index) => (
          <Tooltip enabled key={index} content={member}>
            <Avatar
              name={member}
              size={"md"}
              className="absolute border"
              style={{ left: `${25 * index}px` }}
            />
          </Tooltip>
        ))}
      </div>

      {!!lengthDiff && (
        <Avatar text={`+ ${lengthDiff}`} size={"md"} variant={"active"} className="z-10" />
      )}
    </div>
  );
}
