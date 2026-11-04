import { Link } from "@/shared/components/ui/link";

import { getIpamNamespaceUrl } from "@/entities/ipam/ip-namespaces/ui/routing/ipam-urls";
import {
  IP_POOL_MEMBER_TYPE_ADDRESS,
  IP_POOL_MEMBER_TYPE_PREFIX,
  type IpPoolData,
  type IpPoolDefaultEntry,
  type IpPoolDefaultValue,
} from "@/entities/resource-manager/domain/model/ip-pool";
import { getIpPoolDefaultEntries } from "@/entities/resource-manager/domain/rules/get-ip-pool-default-entries";
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
    <SchemaReference schema={schema} className={schemaLinkStyle}>
      {kind}
    </SchemaReference>
  );
}

interface DefaultValueProps {
  value: IpPoolDefaultValue;
}

function DefaultValue({ value }: DefaultValueProps) {
  if (value.type === "kind") return <KindReference kind={value.kind} />;
  if (value.type === "prefix-length") return <span className="tabular-nums">/{value.length}</span>;
  return <>{MEMBER_TYPE_LABELS[value.memberType]}</>;
}

interface DefaultPhraseProps {
  entry: IpPoolDefaultEntry;
}

function DefaultPhrase({ entry }: DefaultPhraseProps) {
  if (entry.value === null) {
    return (
      <span className="text-foreground-muted">
        {entry.label} {entry.fallbackPhrase}
      </span>
    );
  }

  return (
    <span className="text-foreground-muted">
      {entry.label} defaults to{" "}
      <span className="text-foreground">
        <DefaultValue value={entry.value} />
      </span>
    </span>
  );
}

function Dot() {
  return (
    <span className="text-foreground-muted/60" aria-hidden>
      ·
    </span>
  );
}

export interface IpPoolDefaultsLineProps {
  pool: IpPoolData;
}

export function IpPoolDefaultsLine({ pool }: IpPoolDefaultsLineProps) {
  return (
    <ul className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
      <li className="text-foreground-muted">
        In namespace{" "}
        <Link
          to={getIpamNamespaceUrl(pool.ip_namespace)}
          className="wrap-anywhere rounded-md font-medium text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring-halo"
        >
          {pool.ip_namespace.display_label}
        </Link>
      </li>
      {getIpPoolDefaultEntries(pool).map((entry) => (
        <li key={entry.label} className="flex items-center gap-x-2">
          <Dot />
          <DefaultPhrase entry={entry} />
        </li>
      ))}
    </ul>
  );
}
