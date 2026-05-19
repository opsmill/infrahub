import { Icon } from "@iconify-icon/react";

import { useLoginWithLdap } from "@/entities/authentication/methods/ldap/login-with-ldap.mutation";
import { CredentialsForm } from "@/entities/authentication/ui/credentials-form";

export interface LdapCredentialsFormProps {
  displayLabel: string;
  icon: string;
  className?: string;
}

export const LdapCredentialsForm = ({
  displayLabel,
  icon,
  className,
}: LdapCredentialsFormProps) => {
  const { mutateAsync } = useLoginWithLdap();
  return (
    <CredentialsForm
      onSubmit={mutateAsync}
      className={className}
      submitLabel={
        <>
          <Icon icon={icon} />
          <span className="ml-2">{displayLabel}</span>
        </>
      }
    />
  );
};
