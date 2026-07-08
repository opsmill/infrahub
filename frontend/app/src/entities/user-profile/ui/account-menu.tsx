import { Icon } from "@iconify-icon/react";
import {
  Button,
  LinkButton,
  Menu,
  MenuItem,
  MenuSeparator,
  MenuTrigger,
  Popover,
  Spinner,
} from "@infrahub/ui";
import {
  CircleUserIcon,
  EllipsisVerticalIcon,
  FileTextIcon,
  InfoIcon,
  LogInIcon,
  LogOutIcon,
} from "lucide-react";
import React from "react";
import { useLocation } from "react-router";

import { queryClient } from "@/shared/api/rest/client";
import { constructPath } from "@/shared/api/rest/fetch";
import { Avatar } from "@/shared/components/display/avatar";
import { Skeleton } from "@/shared/components/loading/skeleton";
import {
  INFRAHUB_DISCORD_URL,
  INFRAHUB_DOC_LOCAL,
  INFRAHUB_GITHUB_URL,
  INFRAHUB_SWAGGER_DOC_URL,
} from "@/shared/config/config";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { useLogoutMutation } from "@/entities/authentication/ui/queries/logout.mutation";
import { AboutModal } from "@/entities/config/ui/about-modal";
import { AppInfo } from "@/entities/config/ui/app-info";
import { useGetAccountProfile } from "@/entities/user-profile/ui/queries/get-account-profile.query";

export const AccountMenu = () => {
  const { isAuthenticated } = useAuth();
  const [isAboutOpen, setIsAboutOpen] = React.useState(false);

  return (
    <>
      {isAuthenticated ? (
        <AuthenticatedAccountMenu onAboutClick={() => setIsAboutOpen(true)} />
      ) : (
        <UnauthenticatedAccountMenu onAboutClick={() => setIsAboutOpen(true)} />
      )}
      <AboutModal isOpen={isAboutOpen} onOpenChange={setIsAboutOpen} />
    </>
  );
};

const CommonMenuItems = ({ onAboutClick }: { onAboutClick: () => void }) => (
  <>
    <MenuItem onAction={onAboutClick}>
      <InfoIcon /> About Infrahub
    </MenuItem>

    <MenuItem href={INFRAHUB_DOC_LOCAL} target="_blank" rel="noreferrer">
      <FileTextIcon /> Infrahub documentation
    </MenuItem>

    <MenuItem href={constructPath("/graphql")}>
      <Icon icon="mdi:graphql" className="text-base" />
      GraphQL Sandbox
    </MenuItem>

    <MenuItem href={INFRAHUB_SWAGGER_DOC_URL} target="_blank" rel="noreferrer">
      <Icon icon="mdi:code-json" className="text-base" />
      Swagger documentation
    </MenuItem>

    <MenuSeparator />

    <MenuItem href={INFRAHUB_GITHUB_URL} target="_blank" rel="noreferrer">
      <Icon icon="mdi:github" className="text-base" />
      GitHub Repository
    </MenuItem>

    <MenuItem href={INFRAHUB_DISCORD_URL} target="_blank" rel="noreferrer">
      <Icon icon="mdi:discord" className="text-base" />
      Join our Discord server
    </MenuItem>
  </>
);

const AppInfoFooter = () => (
  <div className="border-stone-300 border-t px-2.5 py-1">
    <AppInfo />
  </div>
);

const UnauthenticatedAccountMenu = ({ onAboutClick }: { onAboutClick: () => void }) => {
  const location = useLocation();

  return (
    <div className="relative">
      <LinkButton
        variant="ghost"
        size="sm"
        className="h-10 w-full justify-stretch gap-2 pr-9 data-pressed:scale-100 group-data-[state=collapsed]:pr-2"
        href="/login"
        routerOptions={{ state: { from: location } }}
      >
        <div className="flex size-6 shrink-0 items-center justify-center overflow-hidden rounded-full bg-stone-200">
          <Icon icon="mdi:user" className="relative top-1 text-3xl text-stone-600" />
        </div>

        <div className="overflow-hidden group-data-[state=collapsed]:hidden">
          <div className="truncate font-medium leading-4">Log in</div>
          <div className="truncate text-stone-500 text-xs">anonymous</div>
        </div>
      </LinkButton>

      <MenuTrigger>
        <Button
          variant="ghost"
          shape="square"
          size="xs"
          data-testid="unauthenticated-menu-trigger"
          className="absolute top-1/2 right-1 -translate-y-1/2 group-data-[state=collapsed]:hidden"
        >
          <EllipsisVerticalIcon />
        </Button>

        <Popover placement="right bottom">
          <Menu variant="picker" aria-label="Account menu">
            <CommonMenuItems onAboutClick={onAboutClick} />
            <MenuSeparator />
            <MenuItem href="/login" routerOptions={{ state: { from: location } }}>
              <LogInIcon />
              Log in
            </MenuItem>
          </Menu>
          <AppInfoFooter />
        </Popover>
      </MenuTrigger>
    </div>
  );
};

const AuthenticatedAccountMenu = ({ onAboutClick }: { onAboutClick: () => void }) => {
  const { setToken } = useAuth();
  const { data: profile, isPending } = useGetAccountProfile();
  const { mutateAsync: logout, isPending: isLoggingOut } = useLogoutMutation();

  const handleSignOut = async () => {
    try {
      await logout();
    } catch (error) {
      console.error("Error when logging out: ", error);
    } finally {
      // Always reset client-side state, even if the server call failed —
      // otherwise a transient error could leave the user with a stale token
      // and another user's cached data still visible.
      setToken(null);
      queryClient.clear();
    }
  };

  if (isPending) {
    return <AccountMenuSkeleton />;
  }

  return (
    <MenuTrigger>
      <Button
        variant="ghost"
        size="sm"
        className="h-10 justify-stretch gap-2 data-pressed:scale-100"
        data-testid="authenticated-menu-trigger"
      >
        <Avatar name={profile?.name?.value} className="size-6" />

        <div className="overflow-hidden group-data-[state=collapsed]:hidden">
          <div className="truncate font-medium text-sm">{profile?.label?.value}</div>
        </div>

        <EllipsisVerticalIcon className="ml-auto group-data-[state=collapsed]:hidden" />
      </Button>

      <Popover placement="right bottom">
        <Menu variant="picker" aria-label="Account menu">
          <MenuItem href={constructPath("/profile")}>
            <CircleUserIcon /> Account settings
          </MenuItem>

          <MenuSeparator />

          <CommonMenuItems onAboutClick={onAboutClick} />

          <MenuSeparator />

          <MenuItem onAction={handleSignOut} isDisabled={isLoggingOut}>
            {isLoggingOut ? <Spinner /> : <LogOutIcon />}
            Logout
          </MenuItem>
        </Menu>
        <AppInfoFooter />
      </Popover>
    </MenuTrigger>
  );
};

const AccountMenuSkeleton = () => {
  return (
    <div className="flex h-10 shrink-0 items-center gap-2 px-2">
      <Skeleton className="size-6 shrink-0 rounded-full" />
      <Skeleton className="h-4 grow group-data-[state=collapsed]:hidden" />
    </div>
  );
};
