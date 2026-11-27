import type { Meta, StoryObj } from "@storybook/react-vite";
import React from "react";
import { Collection } from "react-aria-components";

import { Card } from "../card/card";
import {
  Table,
  TableBody,
  TableCell,
  TableColumn,
  TableEmptyMessage,
  TableHeader,
  TableLink,
  TableLoadMoreItem,
  TableRow,
} from "./table";

const meta: Meta<typeof Table> = {
  component: Table,
  parameters: {
    layout: "padded",
  },
};

export default meta;

type Story = StoryObj<typeof meta>;

const FIRST_NAMES = ["Ada", "Grace", "Alan", "Margaret", "Linus", "Barbara", "Dennis", "Radia"];
const LAST_NAMES = ["Lovelace", "Hopper", "Turing", "Hamilton", "Torvalds", "Liskov", "Ritchie"];
const ROLES = ["Owner", "Editor", "Viewer"];

const MEMBERS = Array.from({ length: 200 }, (_, index) => {
  const firstName = FIRST_NAMES[index % FIRST_NAMES.length];
  const lastName = LAST_NAMES[index % LAST_NAMES.length];

  return {
    id: `member-${index}`,
    name: `${firstName} ${lastName}`,
    email:
      index % 5 === 0
        ? `${firstName}.${lastName}.network-engineering-and-infrastructure-automation-department-${index}@example.com`.toLowerCase()
        : `${firstName}.${lastName}@example.com`.toLowerCase(),
    role: ROLES[index % ROLES.length],
    lastActive: index % 4 === 0 ? null : `${(index % 28) + 1} days ago`,
  };
});

type Member = (typeof MEMBERS)[number];

interface MembersTableProps {
  members: Member[];
  loadMore?: React.ReactNode;
}

function MembersTable({ members, loadMore }: MembersTableProps) {
  return (
    <Table aria-label="Team members">
      <TableHeader>
        <TableColumn isRowHeader>Name</TableColumn>
        <TableColumn width="2fr">Email</TableColumn>
        <TableColumn>Role</TableColumn>
        <TableColumn>Last active</TableColumn>
      </TableHeader>
      <TableBody
        renderEmptyState={() => <TableEmptyMessage>No team members yet</TableEmptyMessage>}
      >
        <Collection items={members}>
          {(member) => (
            <TableRow id={member.id}>
              <TableCell textValue={member.name}>
                <TableLink href={`#${member.id}`}>{member.name}</TableLink>
              </TableCell>
              <TableCell>{member.email}</TableCell>
              <TableCell>{member.role}</TableCell>
              <TableCell>{member.lastActive ?? "-"}</TableCell>
            </TableRow>
          )}
        </Collection>
        {loadMore}
      </TableBody>
    </Table>
  );
}

export const Virtualized: Story = {
  render: () => (
    <Card className="h-96 overflow-hidden">
      <MembersTable members={MEMBERS} />
    </Card>
  ),
};

export const Empty: Story = {
  render: () => (
    <Card className="overflow-hidden">
      <MembersTable members={[]} />
    </Card>
  ),
};

const MEMBERS_PER_PAGE = 30;
const PAGE_LOAD_DELAY_MS = 1000;

function LoadMoreTable() {
  const [loadedCount, setLoadedCount] = React.useState(MEMBERS_PER_PAGE);
  const [isLoadingMore, setIsLoadingMore] = React.useState(false);

  const loadMore = () => {
    if (isLoadingMore) return;

    setIsLoadingMore(true);
    setTimeout(() => {
      setLoadedCount((count) => count + MEMBERS_PER_PAGE);
      setIsLoadingMore(false);
    }, PAGE_LOAD_DELAY_MS);
  };

  return (
    <Card className="h-96 overflow-hidden">
      <MembersTable
        members={MEMBERS.slice(0, loadedCount)}
        loadMore={
          loadedCount < MEMBERS.length && (
            <TableLoadMoreItem onLoadMore={loadMore} isLoading={isLoadingMore} />
          )
        }
      />
    </Card>
  );
}

export const LoadMore: Story = {
  render: () => <LoadMoreTable />,
};
