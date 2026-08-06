// Maps custom GraphQL scalars to their TypeScript representation for gql.tada.
// The generated graphql-env.d.ts only declares `introspection`; this augmentation
// merges scalar overrides into the same `setupSchema` interface so documents using
// these scalars infer concrete types instead of `unknown`.
import "gql.tada";

declare module "gql.tada" {
  interface setupSchema {
    scalars: {
      NonNegativeInt: number;
    };
  }
}
