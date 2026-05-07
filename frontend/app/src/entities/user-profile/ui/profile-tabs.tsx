import { Row } from "@/shared/components/container";
import { LinkTab } from "@/shared/components/ui/link";

export function ProfileTabs() {
  return (
    <Row className="border-gray-200 border-b">
      <LinkTab href="/profile">Profile</LinkTab>
      <LinkTab href="/profile/tokens">Tokens</LinkTab>
      <LinkTab href="/profile/password">Password</LinkTab>
    </Row>
  );
}
