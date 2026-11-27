import type React from "react";

import { Link } from "@/shared/components/ui/link";

import { getIpamNamespaceUrl } from "@/entities/ipam/ip-namespaces/ui/routing/ipam-urls";
import {
  IP_POOL_MEMBER_TYPE_ADDRESS,
  IP_POOL_MEMBER_TYPE_PREFIX,
  type IpAddressPoolData,
  type IpPoolData,
  type IpPoolMemberType,
  type IpPrefixPoolData,
} from "@/entities/resource-manager/domain/model/ip-pool";
import { IP_ADDRESS_POOL } from "@/entities/resource-manager/domain/model/pool";
import {
  IpPoolField,
  IpPoolFieldList,
  UNSET_FIELD_VALUE,
} from "@/entities/resource-manager/ui/ip-pool/details/ip-pool-field";
import {
  SchemaReference,
  schemaLinkStyle,
} from "@/entities/resource-manager/ui/pool/schema-reference";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

const MEMBER_TYPE_LABELS = {
  [IP_POOL_MEMBER_TYPE_PREFIX]: "Prefix",
  [IP_POOL_MEMBER_TYPE_ADDRESS]: "Address",
} as const;

interface KindReferenceProps {
  kind: string;
}

function KindReference({ kind }: KindReferenceProps) {
  const { schema } = useSchema(kind);

  return (
    <SchemaReference
      schema={schema}
      className={`${schemaLinkStyle} max-w-full truncate align-bottom`}
    >
      <span title={kind}>{kind}</span>
    </SchemaReference>
  );
}

interface KindFieldProps {
  label: string;
  kind: string | null;
}

function KindField({ label, kind }: KindFieldProps) {
  return (
    <IpPoolField label={label}>
      {kind ? <KindReference kind={kind} /> : UNSET_FIELD_VALUE}
    </IpPoolField>
  );
}

interface PrefixLengthFieldProps {
  length: number | null;
  unsetValue: React.ReactNode;
}

function PrefixLengthField({ length, unsetValue }: PrefixLengthFieldProps) {
  return (
    <IpPoolField label="Default prefix length">
      {length === null ? unsetValue : <span className="tabular-nums">/{length}</span>}
    </IpPoolField>
  );
}

interface MemberTypeFieldProps {
  memberType: IpPoolMemberType | null;
}

function MemberTypeField({ memberType }: MemberTypeFieldProps) {
  return (
    <IpPoolField label="Default member type">
      {memberType ? MEMBER_TYPE_LABELS[memberType] : UNSET_FIELD_VALUE}
    </IpPoolField>
  );
}

interface PrefixPoolDefaultFieldsProps {
  pool: IpPrefixPoolData;
}

function PrefixPoolDefaultFields({ pool }: PrefixPoolDefaultFieldsProps) {
  return (
    <>
      <KindField label="Default prefix kind" kind={pool.default_prefix_type.value} />
      <PrefixLengthField length={pool.default_prefix_length.value} unsetValue={UNSET_FIELD_VALUE} />
      <MemberTypeField memberType={pool.default_member_type.value} />
    </>
  );
}

interface AddressPoolDefaultFieldsProps {
  pool: IpAddressPoolData;
}

function AddressPoolDefaultFields({ pool }: AddressPoolDefaultFieldsProps) {
  return (
    <>
      <KindField label="Default address kind" kind={pool.default_address_type.value} />
      <PrefixLengthField
        length={pool.default_prefix_length.value}
        unsetValue="Follows the resource prefix"
      />
    </>
  );
}

export interface IpPoolDefaultFieldsProps {
  pool: IpPoolData;
}

export function IpPoolDefaultFields({ pool }: IpPoolDefaultFieldsProps) {
  return (
    <IpPoolFieldList>
      <IpPoolField label="Namespace">
        <Link
          to={getIpamNamespaceUrl(pool.ip_namespace)}
          title={pool.ip_namespace.display_label}
          className="rounded-md text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring-halo"
        >
          {pool.ip_namespace.display_label}
        </Link>
      </IpPoolField>
      {pool.__typename === IP_ADDRESS_POOL ? (
        <AddressPoolDefaultFields pool={pool} />
      ) : (
        <PrefixPoolDefaultFields pool={pool} />
      )}
    </IpPoolFieldList>
  );
}
