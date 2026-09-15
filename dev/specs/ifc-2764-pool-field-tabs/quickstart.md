# Trying it out — every case, in plain language

## What this feature does

A resource pool creates objects of one kind by default. If a relationship points at a
*generic* IP kind, several concrete kinds are allowed, so you should be able to say
"allocate from this pool, but make it a `InfraLoopbackAddress` instead of the pool's usual
`IpamIPAddress`". That is the override.

Along the way the form changed: a field that can use a pool now shows **two tabs** — fill the
value in yourself, or allocate from a pool.

## Setup (once)

```bash
# 1. backend
cd ~/.claude-worktrees/infrahub-ple-ifc-2764-pool-kind-override
INFRAHUB_IMAGE_VER=local uv run invoke demo.start --wait

# 2. schema + demo data
export INFRAHUB_ADDRESS=http://localhost:8000
export INFRAHUB_API_TOKEN=06438eb2-8019-4776-878c-0941b1f1d1ec
uv run infrahubctl schema load models/base models/examples/ipam_kind_override.yml --wait 30
uv run infrahubctl run models/examples/ipam_kind_override_data.py

# 3. frontend
cd frontend/app && pnpm start        # http://localhost:8080
```

Log in with `admin` / `infrahub`.

The demo data gives you two pools whose defaults are deliberately the **`Ipam`** kinds, so if
an override works you get an `Infra` kind back and can tell the difference at a glance:

| Pool | Default kind |
|---|---|
| IFC-2764 demo address pool | `IpamIPAddress` |
| IFC-2764 demo prefix pool | `IpamIPPrefix` |

---

## Part 1 — cases you can try right now

### Case 1: the override works

**Where**: Kind Override Demo → *Create* → the **IP Address** field.

1. Click the **From pool** tab.
2. Pick *IFC-2764 demo address pool*.
3. Under **Type to allocate**, pick `Loopback Address`.
4. Name the object and save.

**You should see**: the linked object is an **`InfraLoopbackAddress`**. The pool's default is
`IpamIPAddress`, so this proves the override took effect.

### Case 2: no override means the pool decides

Same as case 1, but leave **Type to allocate** alone.

**You should see**: an **`IpamIPAddress`** — the pool's default. This is why the control shows
the default as its placeholder: empty means "let the pool decide".

### Case 3: same thing for prefixes

Same as case 1, on the **IP Prefix** field, picking `Transit Prefix`.

**You should see**: an **`InfraTransitPrefix`** instead of the default `IpamIPPrefix`.

### Case 4: you don't have to choose a Kind to use a pool

On the **IP Address** field, click **From pool** straight away, without touching the **Object**
tab.

**You should see**: the pool selector works immediately. This is the fix for the confusing bit —
previously you had to choose a Kind first, and that Kind had nothing to do with which pool you
could pick.

### Case 5: the Kind picker is only for choosing an existing object

Click the **Object** tab.

**You should see**: a **Kind** picker (needed to know which kind of object to search for), and
no pool. Click **From pool** again and the Kind picker is gone. The two tabs no longer
contradict each other.

### Case 6: switching tabs clears what you staged

Pick a pool in **From pool**, then click **Object**, then go back.

**You should see**: your pool choice is gone. A field can't be both filled in *and* allocated,
so switching starts that mode fresh.

### Case 7: a concrete relationship gets a pool but no kind override

**Where**: Device → *Create* → the **Primary Address** field. That relationship points at
`IpamIPAddress` directly, not at the generic.

**You should see**: a pool button (this field hasn't moved to tabs yet — see Part 3), a prefix
length override, and **no kind override**. There is nothing to choose: the relationship already
says exactly which kind it wants.

### Case 8: a "many" relationship gets no pool at all

**Where**: Interface L3 → *Create* → **IP Addresses** (accepts several values).

**You should see**: no pool option anywhere. Pools only apply to fields holding one value.

### Case 9: an unrelated relationship gets no pool

**Where**: Device → *Create* → **Site** or **Platform**.

**You should see**: no pool option. Nothing to do with IP addressing.

### Case 10: a bad kind is refused by the server

This one needs GraphQL, at http://localhost:8000/graphql.

```graphql
mutation {
  InfraKindOverrideDemoCreate(data: {
    name: {value: "bad-kind-test"},
    ip_address: {from_pool: {id: "<address pool id>", address_type: "InfraDevice"}}
  }) { ok }
}
```

**You should see**: an error saying `'InfraDevice' is not a valid kind to allocate for
'BuiltinIPAddress', allowed kinds are ['InfraLoopbackAddress', 'IpamIPAddress']`. The UI can't
produce this — it only offers valid kinds — but the server refuses it anyway, so the API is safe
on its own.

### Case 11: a reservation keeps the kind it was created with

```graphql
mutation {
  InfrahubIPAddressPoolGetResource(data: {
    id: "<address pool id>", identifier: "my-slot",
    address_type: "IpamIPAddress", prefix_length: 32
  }) { ok node { kind display_label } }
}
```

Run it once, then again with `address_type: "InfraLoopbackAddress"`.

**You should see**: the first call allocates an `IpamIPAddress`. Running it again with the *same*
kind returns the same address. Running it with a *different* kind is **refused** — an allocation
that already exists can't change kind.

### Case 12: an existing allocation can't be re-cut

Open one of the objects you created in case 1, and look at the same field.

**You should see**: the **From pool** tab active, naming the pool, and **no** override controls.
The allocation already happened; its kind and mask are fixed.

---

## Part 2 — cases that need work I haven't done yet

These are real rules, already true in the code, but the demo schema has no shape that lets you
reach them by hand. Building those shapes is the "harness" task still outstanding.

| Case | What should happen | Why you can't try it yet |
|---|---|---|
| Generic with only **one** concrete kind | Pool offered, **no** kind override — nothing to override | No such generic in the demo schema |
| An `address`/`prefix` **attribute** (not a relationship) | Pool offered **when creating**, not when editing | No demo node has one |
| A **number** field with a number pool | Pool offered, **neither** override applies | No demo node has one |
| An **object template** over a pool-backed relationship | Allocates the pool default; overrides not supported (IFC-3135) | No demo template |
| A value inherited from a **template** that references a pool | Pool shown for provenance, but not submitted | Needs the template above |

---

## Part 3 — known rough edges

- **Only the generic relationship field has tabs so far.** `Number`, `prefix`/`address`
  attributes, the regular relationship field and the hierarchical one still show the old pool
  button. Migrating all four is the remaining work; until then the form is inconsistent, which
  is expected mid-change and not a bug to report.
- **A field you're not allowed to edit still shows a live pool button** on those four
  unmigrated fields. That's a pre-existing bug the tab work fixes as it goes.
- **Opening a form on the right tab** relies on the stored value saying where it came from.
  There is a case where a pool-allocated value is recorded as if you typed it, which would open
  the wrong tab. Harmless before (the pool was just a button), so it may still be there — worth
  a look if you see a pool-allocated value open on the **Object** tab.
