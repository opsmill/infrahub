import { Button } from "@/components/buttons/button-primitive";
import { Avatar } from "@/components/display/avatar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tooltip } from "@/components/ui/tooltip";

interface GroupMembersProps {
  members: Array<string>;
}

export function GroupMembers({ members }: GroupMembersProps) {
  const trimedMembers = members.slice(0, 5);
  const restOfItems = members.slice(5);

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
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" size={"icon"}>{`+${lengthDiff}`}</Button>
          </PopoverTrigger>

          <PopoverContent align="start">
            <div className="flex gap-2">
              {restOfItems.map((item, index) => (
                <Tooltip enabled key={index} content={item}>
                  <Avatar name={item} size={"md"} />
                </Tooltip>
              ))}
            </div>
          </PopoverContent>
        </Popover>
      )}
    </div>
  );
}
