import { Row } from "@/shared/components/container";
import { LinkTab } from "@/shared/components/ui/link";

export function ProfileTabs() {
  return (
    <nav aria-label="Tabs">
      <Row className="border-gray-200 border-b">
        <LinkTab to="/profile">Profile</LinkTab>
        <LinkTab to="/profile/tokens">Tokens</LinkTab>
        <LinkTab to="/profile/password">Password</LinkTab>
      </Row>
    </nav>
  );
}
