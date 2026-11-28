# Round 5 feedback: schema-tab rev 2

Source: notes written by the owner in the design-jam session on 2026-11-17, copied word for
word.

1. add relevant links between srceen if more details are available in another view
2. in schema viewer we must have 1 tab button to switch between the 4 views
3. in schema viewer it seems weird to have current, staged and list views, all of them are
   more or less displaying the schema but in different ways, what could be done to improve
   that here
4. in branch view i dont understand why we have staged and staged + applying, both are
   showing the same data but in different state and the views are really different, what
   can be done to improve that

## Triage, 2026-11-17

1. Links between screens: **addressed** in schema-tab rev 3. The list of links is in
   `03-decisions.md`, "Links between screens". Links in the prototype change the Screen
   knob.
2. One toggle in the schema viewer: **addressed** in rev 3: "List | Graph | Staged".
3. Current, Staged and List overlap: **addressed** in rev 3. "Current" was the same view as
   List and is removed. Staged uses the List layout, with the differences marked. Another
   option, not built: no Staged option, and a "Show the staged change" switch inside List.
4. Staged and "Staged · applying" look different: **addressed** in rev 3. One Staged layout;
   the "Staged change" knob switches between staged, applying and applied. The "Branch:
   Apply running" screen is removed from the Screen knob, and revs 1 and 2 show it when
   Staged change is "applying".

Awaiting the owner's review of rev 3.
