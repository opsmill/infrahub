# IFC-2090: Get Relationships in Frontend for Profiles

## Summary

Currently, when selecting profiles in the frontend form, only attributes are queried. We need to also query relationships so that profile relationships populate the form fields when creating or updating objects.

## Current State

### How Profiles Work Now

1. **profiles-selector.tsx** (line 72-73):
   - Uses `getObjectAttributes({ schema: profileSchema, forProfiles: true })` to get only attributes
   - Passes attributes to `getProfiles()` Handlebars template

2. **getProfiles.ts**: The GraphQL template only queries attributes:
   ```graphql
   {{#each profiles}}
     {{this.name}} {
       edges {
         node {
           id
           display_label
           {{#each this.attributes}}
             {{this.name}} { value ... }
           {{/each}}
         }
       }
     }
   {{/each}}
   ```

3. **getFieldDefaultValue.ts** (line 103-136):
   - `getDefaultValueFromProfiles()` extracts attribute values from profile data
   - No equivalent for relationships

4. **getRelationshipDefaultValue.ts**:
   - Gets relationship defaults from data, templates, or pools
   - **No profile support**

## Implementation Plan

### Step 1: Update `getProfiles.ts` to Include Relationships

Modify the Handlebars template to query relationships in addition to attributes:

```handlebars
{{#each profiles}}
  {{this.name}} {
    edges {
      node {
        id
        display_label

        {{#each this.attributes}}
          {{this.name}} { value ... }
        {{/each}}

        {{#each this.relationships}}
          {{this.name}} {
            node {
              id
              display_label
              __typename
            }
          }
        {{/each}}
      }
    }
  }
{{/each}}
```

### Step 2: Update `profiles-selector.tsx` to Pass Relationships

Modify the profile list building to include relationships:

1. Add import for `getObjectRelationships` or create a new function `getProfileRelationships`
2. Get relationships for each profile schema (filtered for form-eligible ones)
3. Pass both attributes and relationships to `getProfiles()`

### Step 3: Add `RelationshipValueFromProfile` Type

In **type.ts**, add:

```typescript
export type RelationshipOneValueFromProfile = {
  source: ProfileSource;
  value: Node | null;
};

export type RelationshipManyValueFromProfile = {
  source: ProfileSource;
  value: Array<Node> | null;
};

export type RelationshipValueFromProfile =
  | RelationshipOneValueFromProfile
  | RelationshipManyValueFromProfile;
```

Update `FormRelationshipValue` to include this type.

### Step 4: Update `getRelationshipDefaultValue.ts`

Add a `getRelationshipDefaultValueFromProfiles()` function similar to `getDefaultValueFromProfiles()` in getFieldDefaultValue.ts:

```typescript
const getRelationshipDefaultValueFromProfiles = (
  relationshipName: string,
  profiles: Array<ProfileData>
): RelationshipValueFromProfile | null => {
  const orderedProfiles = R.sortBy(
    profiles,
    (profile) => profile.profile_priority?.value ?? 0,
    (profile) => profile.id
  );

  const profileWithDefaultValueForField = R.find(orderedProfiles, (profile) => {
    const profileRelationshipData = profile[relationshipName];
    if (!profileRelationshipData) return false;
    return profileRelationshipData.node !== null;
  });

  if (!profileWithDefaultValueForField) return null;

  const relationshipData = profileWithDefaultValueForField[relationshipName];

  return {
    source: {
      type: "profile",
      id: profileWithDefaultValueForField.id,
      label: profileWithDefaultValueForField.display_label,
      kind: profileWithDefaultValueForField.__typename,
    },
    value: relationshipData.node,
  };
};
```

Update `getRelationshipDefaultValue()` to call this function in the fallback chain.

### Step 5: Update `getFormFieldFromRelationship.ts`

Pass profiles to the function and use them when getting default values.

### Step 6: Update `getFormFieldsFromSchema.ts`

Pass profiles to `getFormFieldFromRelationship()` calls.

## Files to Modify

| File | Changes |
|------|---------|
| `src/entities/nodes/api/getProfiles.ts` | Add relationships to GraphQL query template |
| `src/shared/components/form/profiles-selector.tsx` | Get and pass relationships data |
| `src/shared/components/form/type.ts` | Add `RelationshipValueFromProfile` type |
| `src/shared/components/form/utils/getRelationshipDefaultValue.ts` | Add profile support |
| `src/shared/components/form/utils/getFormFieldFromRelationship.ts` | Accept profiles parameter |
| `src/shared/components/form/utils/getFormFieldsFromSchema.ts` | Pass profiles to relationship fields |

## Testing Strategy

Unit tests for:
1. `getProfiles.ts` - Verify relationships are included in query output
2. `getRelationshipDefaultValue.ts` - Test `getRelationshipDefaultValueFromProfiles()` function
3. Verify profile priority ordering works for relationships (same as attributes)

## Notes

- Follow the same pattern as attributes: ordered by `profile_priority.value`
- Only include relationships that are form-eligible (cardinality "one" or kind "Attribute"/"Parent")
- Profile relationships should only have cardinality "one" since profiles are meant to provide default values
