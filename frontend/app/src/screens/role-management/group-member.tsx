import { Avatar } from "@/components/display/avatar";

interface GroupMembersProps {
  members: Array<string>;
}

export function GroupMembers({ members }: GroupMembersProps) {
  const trimedMembers = members.slice(0, 5);

  const lengthDiff = members.length - trimedMembers.length;

  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center relative w-28 h-12">
        {trimedMembers.map((member, index) => (
          <Avatar
            name={member}
            key={index}
            size={"md"}
            className="absolute border"
            style={{ left: `${20 * index}px` }}
          />
        ))}
      </div>

      {lengthDiff && (
        <Avatar text={`+ ${lengthDiff}`} size={"md"} variant={"active"} className="z-10" />
      )}
    </div>
  );
}
