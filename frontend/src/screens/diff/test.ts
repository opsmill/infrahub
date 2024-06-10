export const text = `
diff --git a/frontend/package-lock.json b/frontend/package-lock.json
index b512778e..22624e2b 100644
--- a/frontend/package-lock.json
+++ b/frontend/package-lock.json
@@ -30,2 +30,3 @@
         "react-datepicker": "^4.11.0",
+        "react-diff-view": "^3.0.3",
         "react-dom": "^18.2.0",
@@ -5362,2 +5363,7 @@
     },
+    "node_modules/diff-match-patch": {
+      "version": "1.0.5",
+      "resolved": "https://registry.npmjs.org/diff-match-patch/-/diff-match-patch-1.0.5.tgz",
+      "integrity": "sha512-IayShXAgj/QMXgB0IWmKx+rOPuGMhqm5w6jvFxmVenXKIzRqTAAsbBPT3kWQeGANj3jGgvcvv4yK6SxqYmikgw=="
+    },
     "node_modules/dir-glob": {
@@ -10228,2 +10234,17 @@
     },
+    "node_modules/react-diff-view": {
+      "version": "3.0.3",
+      "resolved": "https://registry.npmjs.org/react-diff-view/-/react-diff-view-3.0.3.tgz",
+      "integrity": "sha512-orETYmQbptfMbOnbkSHH61Ew5RBTYWAO2M1MDx2ZvsEDHPygn6U8mWh7kUCm/z40YzVKmd3+8hpH872Y0uioIg==",
+      "dependencies": {
+        "classnames": "^2.3.2",
+        "diff-match-patch": "^1.0.5",
+        "shallow-equal": "^3.1.0",
+        "warning": "^4.0.3"
+      },
+      "peerDependencies": {
+        "prop-types": ">=15.6",
+        "react": ">=16.8"
+      }
+    },
     "node_modules/react-dom": {
@@ -10763,2 +10784,7 @@
     },
+    "node_modules/shallow-equal": {
+      "version": "3.1.0",
+      "resolved": "https://registry.npmjs.org/shallow-equal/-/shallow-equal-3.1.0.tgz",
+      "integrity": "sha512-pfVOw8QZIXpMbhBWvzBISicvToTiM5WBF1EeAUZDDSb5Dt29yl4AYbyywbJFSEsRUMr7gJaxqCdr4L3tQf9wVg=="
+    },
     "node_modules/shebang-command": {
@@ -16288,2 +16314,7 @@
     },
+    "diff-match-patch": {
+      "version": "1.0.5",
+      "resolved": "https://registry.npmjs.org/diff-match-patch/-/diff-match-patch-1.0.5.tgz",
+      "integrity": "sha512-IayShXAgj/QMXgB0IWmKx+rOPuGMhqm5w6jvFxmVenXKIzRqTAAsbBPT3kWQeGANj3jGgvcvv4yK6SxqYmikgw=="
+    },
     "dir-glob": {
@@ -19797,2 +19828,13 @@
     },
+    "react-diff-view": {
+      "version": "3.0.3",
+      "resolved": "https://registry.npmjs.org/react-diff-view/-/react-diff-view-3.0.3.tgz",
+      "integrity": "sha512-orETYmQbptfMbOnbkSHH61Ew5RBTYWAO2M1MDx2ZvsEDHPygn6U8mWh7kUCm/z40YzVKmd3+8hpH872Y0uioIg==",
+      "requires": {
+        "classnames": "^2.3.2",
+        "diff-match-patch": "^1.0.5",
+        "shallow-equal": "^3.1.0",
+        "warning": "^4.0.3"
+      }
+    },
     "react-dom": {
@@ -20182,2 +20224,7 @@
     },
+    "shallow-equal": {
+      "version": "3.1.0",
+      "resolved": "https://registry.npmjs.org/shallow-equal/-/shallow-equal-3.1.0.tgz",
+      "integrity": "sha512-pfVOw8QZIXpMbhBWvzBISicvToTiM5WBF1EeAUZDDSb5Dt29yl4AYbyywbJFSEsRUMr7gJaxqCdr4L3tQf9wVg=="
+    },
     "shebang-command": {
diff --git a/frontend/package.json b/frontend/package.json
index e2e87ee0..724c162b 100644
--- a/frontend/package.json
+++ b/frontend/package.json
@@ -47,2 +47,3 @@
     "react-datepicker": "^4.11.0",
+    "react-diff-view": "^3.0.3",
     "react-dom": "^18.2.0",
diff --git a/frontend/src/screens/branches/diff/diff.tsx b/frontend/src/screens/branches/diff/diff.tsx
index c122eae0..429919bb 100644
--- a/frontend/src/screens/branches/diff/diff.tsx
+++ b/frontend/src/screens/branches/diff/diff.tsx
@@ -7,2 +7,3 @@ import { DynamicFieldData } from "../../edit-form-hook/dynamic-control-types";
 import { DataDiff } from "./data-diff";
+import { FilesDiff } from "./files-diff";
 import { SchemaDiff } from "./schema-diff";
@@ -53,4 +54,3 @@ const renderContent = (tab: string | null | undefined) => {
     case DIFF_TABS.FILES:
-      // return <FilesDiff />;
-      return null;
+      return <FilesDiff />;
     case DIFF_TABS.SCHEMA:
diff --git a/frontend/src/screens/branches/diff/files-diff.tsx b/frontend/src/screens/branches/diff/files-diff.tsx
index 25392af1..2788585a 100644
--- a/frontend/src/screens/branches/diff/files-diff.tsx
+++ b/frontend/src/screens/branches/diff/files-diff.tsx
@@ -1,66 +1,104 @@
-import { useParams } from "react-router-dom";
-import { useCallback, useEffect, useState } from "react";
-import { DataDiffNode } from "./data-diff-node";
-import { CONFIG } from "@/config/config";
-import { fetchUrl } from "@/utils/fetch";
-import { QSP } from "@/config/qsp";
-import { StringParam, useQueryParam } from "use-query-params";
-import LoadingScreen from "../../loading-screen/loading-screen";
-import { toast } from "react-toastify";
-import { ALERT_TYPES, Alert } from "@/components/alert";
+import { PencilIcon } from "@heroicons/react/24/outline";
+import { Diff, Hunk, getChangeKey, parseDiff } from "react-diff-view";
+import "react-diff-view/style/index.css";
+import { Button } from "@/components/button";
+import { text as diffText } from "./test";
+
+const comments = [
+  {
+    oldLineNumber: 47,
+    message: "Very interesting comment here",
+  },
+  {
+    lineNumber: 48,
+    message: "An interesting comment here",
+  },
+  {
+    lineNumber: 48,
+    message: "Again another one",
+  },
+];

 export const FilesDiff = () => {
-  const { branchname } = useParams();
-  const [diff, setDiff] = useState([]);
-  const [isLoading, setIsLoading] = useState(false);
-  const [branchOnly] = useQueryParam(QSP.BRANCH_FILTER_BRANCH_ONLY, StringParam);
-  const [timeFrom] = useQueryParam(QSP.BRANCH_FILTER_TIME_FROM, StringParam);
-  const [timeTo] = useQueryParam(QSP.BRANCH_FILTER_TIME_TO, StringParam);
+  const files = parseDiff(diffText);
+
+  const getWidgets = (hunks: any) => {
+    const changes = hunks.reduce((result: any, { changes }: any) => [...result, ...changes], []);

-  const fetchDiffDetails = useCallback(async () => {
-    if (!branchname) return;
+    const changesWithComments = changes
+      .map((change: any) => {
+        const relatedComments = comments.filter(
+          (comment) =>
+            (comment.newLineNumber &&
+              change.newLineNumber &&
+              comment.newLineNumber === change.newLineNumber) ||
+            (comment.oldLineNumber &&
+              change.oldLineNumber &&
+              comment.oldLineNumber === change.oldLineNumber) ||
+            (comment.lineNumber && change.lineNumber && comment.lineNumber === change.lineNumber)
+        );

-    setIsLoading(true);
+        if (relatedComments?.length) {
+          return {
+            ...change,
+            comments: relatedComments,
+          };
+        }

-    const url = CONFIG.FILES_DIFF_URL(branchname);
+        return null;
+      })
+      .filter(Boolean);

-    const options: string[][] = [
-      ["branch_only", branchOnly ?? ""],
-      ["time_from", timeFrom ?? ""],
-      ["time_to", timeTo ?? ""],
-    ].filter(([k, v]) => v !== undefined && v !== "");
+    return changesWithComments.reduce((widgets: any, change: any) => {
+      const changeKey = getChangeKey(change);

-    const qsp = new URLSearchParams(options);
+      if (!change.comments) {
+        return widgets;
+      }

+      return {
+        ...widgets,
+        [changeKey]: change?.comments?.map((comment: any, index: number) => (
+          <div key={index} className="bg-custom-white p-4">
+            {comment.message}
+          </div>
+        )),
+      };
+    }, {});
+  };

-    try {
-      const diffDetails = await fetchUrl(urlWithQsp);
+  const renderGutter = (options: any) => {
+    const { change, side, renderDefault, wrapInAnchor, inHoverState } = options;

-      setDiff(diffDetails[branchname] ?? []);
-    } catch (err) {
-      console.error("err: ", err);
-      toast(<Alert type={ALERT_TYPES.ERROR} message="Error while loading branch diff" />);
-    }
+    return (
+      <>
+        {wrapInAnchor(renderDefault())}

-    setIsLoading(false);
-  }, [branchname, branchOnly, timeFrom, timeTo]);
+        {inHoverState && (
+          <Button className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2">
+            <PencilIcon className="w-3 h-3" />
+          </Button>
+        )}
+      </>
+    );
+  };

-  useEffect(() => {
-    fetchDiffDetails();
-  }, [fetchDiffDetails]);
+  const renderFile = (options: any) => {
+    const { oldRevision, newRevision, type, hunks } = options;

-  return (
-    <>
-      {isLoading && <LoadingScreen />}
+    return (
+      <Diff
+        key={oldRevision + "-" + newRevision}
+        viewType="split"
+        diffType={type}
+        hunks={hunks}
+        renderGutter={renderGutter}
+        widgets={getWidgets(hunks)}
+        optimizeSelection>
+        {(hunks) => hunks.map((hunk) => <Hunk key={hunk.content} hunk={hunk} />)}
+      </Diff>
+    );
+  };

-      {!isLoading && (
-        <div>
-          {diff?.map((node: any, index: number) => (
-            <DataDiffNode key={index} node={node} />
-          ))}
-        </div>
-      )}
-    </>
-  );
+  return <div>{files.map(renderFile)}</div>;
 };
diff --git a/frontend/src/styles/index.css b/frontend/src/styles/index.css
index d4264232..0e07d8e9 100644
--- a/frontend/src/styles/index.css
+++ b/frontend/src/styles/index.css
@@ -1,2 +1,3 @@
 @import "./Alert.css";
+@import "./DiffView.css";
`;
