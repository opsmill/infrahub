var InfrahubPluginExport = (function(exports, jsxRuntime, reactRouter) {
  "use strict";
  const manifest$1 = {
    id: "example-quick-stats",
    name: "Quick Stats",
    kinds: ["InfraDevice"],
    position: "panel",
    panelTitle: "Quick Stats",
    icon: "mdi:chart-bar",
    priority: 5
  };
  function QuickStatsPlugin({
    object,
    schema,
    objectData
  }) {
    var _a, _b, _c, _d, _e;
    const attributeCount = ((_a = schema.attributes) == null ? void 0 : _a.length) ?? 0;
    const relationshipCount = ((_b = schema.relationships) == null ? void 0 : _b.length) ?? 0;
    const deviceName = ((_c = objectData == null ? void 0 : objectData.name) == null ? void 0 : _c.value) ?? object.displayLabel;
    const description = (_d = objectData == null ? void 0 : objectData.description) == null ? void 0 : _d.value;
    return /* @__PURE__ */ jsxRuntime.jsxs("div", { className: "space-y-3", children: [
      /* @__PURE__ */ jsxRuntime.jsxs("div", { className: "grid grid-cols-3 gap-4 text-center", children: [
        /* @__PURE__ */ jsxRuntime.jsxs("div", { children: [
          /* @__PURE__ */ jsxRuntime.jsx("div", { className: "text-2xl font-bold text-blue-600", children: attributeCount }),
          /* @__PURE__ */ jsxRuntime.jsx("div", { className: "text-xs text-gray-500", children: "Attributes" })
        ] }),
        /* @__PURE__ */ jsxRuntime.jsxs("div", { children: [
          /* @__PURE__ */ jsxRuntime.jsx("div", { className: "text-2xl font-bold text-green-600", children: relationshipCount }),
          /* @__PURE__ */ jsxRuntime.jsx("div", { className: "text-xs text-gray-500", children: "Relationships" })
        ] }),
        /* @__PURE__ */ jsxRuntime.jsxs("div", { children: [
          /* @__PURE__ */ jsxRuntime.jsx("div", { className: "text-2xl font-bold text-purple-600", children: ((_e = object.id) == null ? void 0 : _e.slice(0, 8)) ?? "N/A" }),
          /* @__PURE__ */ jsxRuntime.jsx("div", { className: "text-xs text-gray-500", children: "ID (short)" })
        ] })
      ] }),
      description && /* @__PURE__ */ jsxRuntime.jsxs("div", { className: "text-gray-600 text-sm border-gray-200 border-t pt-2", children: [
        /* @__PURE__ */ jsxRuntime.jsxs("span", { className: "font-medium", children: [
          deviceName,
          ":"
        ] }),
        " ",
        description
      ] })
    ] });
  }
  const manifest = {
    id: "example-device-info",
    name: "Device Visualization",
    kinds: ["InfraDevice"],
    position: "tab",
    tabLabel: "Visualization",
    icon: "mdi:server",
    priority: 10,
    query: {
      type: "inline",
      query: `
      query GetDeviceInfo($ids: [ID!]) {
        InfraDevice(ids: $ids) {
          edges {
            node {
              id
              display_label
              name { value }
              description { value }
              status { value }
              interfaces {
                count
                edges {
                  node {
                    id
                    display_label
                    name {
                      value
                    }
                    role {
                      value
                    }
                    enabled {
                      value
                    }
                    speed {
                      value
                    }
                  }
                }
              }
            }
          }
        }
      }
    `
    }
  };
  const ROLE_COLORS = {
    backbone: {
      bg: "bg-purple-100 hover:bg-purple-200",
      border: "border-purple-400",
      text: "text-purple-800",
      label: "Backbone"
    },
    upstream: {
      bg: "bg-blue-100 hover:bg-blue-200",
      border: "border-blue-400",
      text: "text-blue-800",
      label: "Upstream"
    },
    peering: {
      bg: "bg-green-100 hover:bg-green-200",
      border: "border-green-400",
      text: "text-green-800",
      label: "Peering"
    },
    peer: {
      bg: "bg-green-100 hover:bg-green-200",
      border: "border-green-400",
      text: "text-green-800",
      label: "Peer"
    },
    server: {
      bg: "bg-orange-100 hover:bg-orange-200",
      border: "border-orange-400",
      text: "text-orange-800",
      label: "Server"
    },
    spare: {
      bg: "bg-gray-100 hover:bg-gray-200",
      border: "border-gray-400",
      text: "text-gray-600",
      label: "Spare"
    },
    loopback: {
      bg: "bg-cyan-100 hover:bg-cyan-200",
      border: "border-cyan-400",
      text: "text-cyan-800",
      label: "Loopback"
    },
    management: {
      bg: "bg-yellow-100 hover:bg-yellow-200",
      border: "border-yellow-400",
      text: "text-yellow-800",
      label: "Management"
    },
    leaf: {
      bg: "bg-emerald-100 hover:bg-emerald-200",
      border: "border-emerald-400",
      text: "text-emerald-800",
      label: "Leaf"
    },
    default: {
      bg: "bg-slate-100 hover:bg-slate-200",
      border: "border-slate-400",
      text: "text-slate-700",
      label: "Unknown"
    }
  };
  function getRoleColors(role) {
    if (!role) return ROLE_COLORS.default;
    const normalizedRole = role.toLowerCase();
    return ROLE_COLORS[normalizedRole] ?? ROLE_COLORS.default;
  }
  function InterfaceSlot({
    iface,
    onClick
  }) {
    var _a, _b, _c;
    const role = (_a = iface.role) == null ? void 0 : _a.value;
    const colors = getRoleColors(role);
    const isEnabled = ((_b = iface.enabled) == null ? void 0 : _b.value) !== false;
    const speed = (_c = iface.speed) == null ? void 0 : _c.value;
    return /* @__PURE__ */ jsxRuntime.jsxs(
      "button",
      {
        onClick,
        className: `
        relative group w-16 h-20 rounded-lg border-2 transition-all duration-200
        ${colors.bg} ${colors.border}
        ${!isEnabled ? "opacity-50" : ""}
        cursor-pointer shadow-sm hover:shadow-md hover:scale-105
        flex flex-col items-center justify-center p-1
      `,
        title: `${iface.name.value}${role ? ` (${role})` : ""}${speed ? ` - ${speed}Mbps` : ""}`,
        children: [
          /* @__PURE__ */ jsxRuntime.jsx(
            "div",
            {
              className: `w-8 h-3 rounded-sm mb-1 ${isEnabled ? "bg-green-500" : "bg-gray-400"}`
            }
          ),
          /* @__PURE__ */ jsxRuntime.jsx("span", { className: `text-xs font-medium ${colors.text} truncate w-full text-center`, children: iface.name.value.replace(/^(Ethernet|eth|GigabitEthernet|Gi|xe-|et-)/, "") }),
          role && /* @__PURE__ */ jsxRuntime.jsx(
            "span",
            {
              className: `text-[9px] ${colors.text} opacity-75 truncate w-full text-center`,
              children: role
            }
          ),
          /* @__PURE__ */ jsxRuntime.jsxs(
            "div",
            {
              className: "\n          absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1\n          bg-gray-900 text-white text-xs rounded shadow-lg\n          opacity-0 group-hover:opacity-100 transition-opacity\n          pointer-events-none whitespace-nowrap z-10\n        ",
              children: [
                iface.display_label || iface.name.value,
                speed && /* @__PURE__ */ jsxRuntime.jsxs("span", { className: "text-gray-400 ml-1", children: [
                  "(",
                  speed,
                  "Mbps)"
                ] })
              ]
            }
          )
        ]
      }
    );
  }
  function DeviceVisualization({
    device,
    onInterfaceClick
  }) {
    var _a;
    const interfaces = device.interfaces.edges.map((e) => e.node);
    const roleGroups = interfaces.reduce(
      (acc, iface) => {
        var _a2, _b;
        const role = ((_b = (_a2 = iface.role) == null ? void 0 : _a2.value) == null ? void 0 : _b.toLowerCase()) ?? "default";
        if (!acc[role]) acc[role] = [];
        acc[role].push(iface);
        return acc;
      },
      {}
    );
    return /* @__PURE__ */ jsxRuntime.jsxs("div", { className: "space-y-6", children: [
      /* @__PURE__ */ jsxRuntime.jsx("div", { className: "", children: /* @__PURE__ */ jsxRuntime.jsxs("div", { className: "bg-white rounded-lg p-4 border border-gray-200", children: [
        /* @__PURE__ */ jsxRuntime.jsxs("div", { className: "flex items-center justify-between mb-4 pb-3 border-b border-gray-700", children: [
          /* @__PURE__ */ jsxRuntime.jsxs("div", { className: "flex items-center gap-3", children: [
            /* @__PURE__ */ jsxRuntime.jsx("div", { className: "w-3 h-3 rounded-full bg-green-500 animate-pulse" }),
            /* @__PURE__ */ jsxRuntime.jsx("span", { className: "text-black font-bold text-lg", children: device.name.value })
          ] }),
          /* @__PURE__ */ jsxRuntime.jsx("div", { className: "flex items-center gap-2", children: ((_a = device.status) == null ? void 0 : _a.value) && /* @__PURE__ */ jsxRuntime.jsx(
            "span",
            {
              className: `px-2 py-0.5 rounded text-xs font-medium ${device.status.value.toLowerCase() === "active" ? "bg-green-600 text-white" : "bg-yellow-600 text-white"}`,
              children: device.status.value
            }
          ) })
        ] }),
        interfaces.length > 0 ? /* @__PURE__ */ jsxRuntime.jsx("div", { className: "flex flex-wrap gap-2 justify-center", children: interfaces.map((iface) => /* @__PURE__ */ jsxRuntime.jsx(
          InterfaceSlot,
          {
            iface,
            onClick: () => onInterfaceClick(iface)
          },
          iface.id
        )) }) : /* @__PURE__ */ jsxRuntime.jsx("div", { className: "text-gray-500 text-center py-8", children: "No interfaces configured" })
      ] }) }),
      Object.keys(roleGroups).length > 0 && /* @__PURE__ */ jsxRuntime.jsxs("div", { className: "bg-white rounded-lg border border-gray-200 p-4 mt-4", children: [
        /* @__PURE__ */ jsxRuntime.jsx("h4", { className: "text-sm font-semibold text-gray-700 mb-3", children: "Interface Roles" }),
        /* @__PURE__ */ jsxRuntime.jsx("div", { className: "flex flex-wrap gap-3", children: Object.entries(roleGroups).map(([role, ifaces]) => {
          const colors = getRoleColors(role);
          return /* @__PURE__ */ jsxRuntime.jsxs(
            "div",
            {
              className: `flex items-center gap-2 px-3 py-1.5 rounded-full border ${colors.bg} ${colors.border}`,
              children: [
                /* @__PURE__ */ jsxRuntime.jsx("div", { className: `w-3 h-3 rounded-full ${colors.border} border-2` }),
                /* @__PURE__ */ jsxRuntime.jsx("span", { className: `text-sm font-medium ${colors.text}`, children: colors.label }),
                /* @__PURE__ */ jsxRuntime.jsxs("span", { className: `text-xs ${colors.text} opacity-70`, children: [
                  "(",
                  ifaces.length,
                  ")"
                ] })
              ]
            },
            role
          );
        }) })
      ] }),
      /* @__PURE__ */ jsxRuntime.jsxs("div", { className: "grid grid-cols-3 gap-4 mt-4", children: [
        /* @__PURE__ */ jsxRuntime.jsxs("div", { className: "bg-blue-50 rounded-lg p-4 text-center", children: [
          /* @__PURE__ */ jsxRuntime.jsx("div", { className: "text-3xl font-bold text-blue-600", children: device.interfaces.count }),
          /* @__PURE__ */ jsxRuntime.jsx("div", { className: "text-sm text-blue-700", children: "Total Interfaces" })
        ] }),
        /* @__PURE__ */ jsxRuntime.jsxs("div", { className: "bg-green-50 rounded-lg p-4 text-center", children: [
          /* @__PURE__ */ jsxRuntime.jsx("div", { className: "text-3xl font-bold text-green-600", children: interfaces.filter((i) => {
            var _a2;
            return ((_a2 = i.enabled) == null ? void 0 : _a2.value) !== false;
          }).length }),
          /* @__PURE__ */ jsxRuntime.jsx("div", { className: "text-sm text-green-700", children: "Enabled" })
        ] }),
        /* @__PURE__ */ jsxRuntime.jsxs("div", { className: "bg-gray-50 rounded-lg p-4 text-center", children: [
          /* @__PURE__ */ jsxRuntime.jsx("div", { className: "text-3xl font-bold text-gray-600", children: interfaces.filter((i) => {
            var _a2;
            return ((_a2 = i.enabled) == null ? void 0 : _a2.value) === false;
          }).length }),
          /* @__PURE__ */ jsxRuntime.jsx("div", { className: "text-sm text-gray-700", children: "Disabled" })
        ] })
      ] })
    ] });
  }
  function DeviceInfoPlugin({
    queryData,
    isQueryLoading,
    queryError
  }) {
    var _a, _b, _c;
    const navigate = reactRouter.useNavigate();
    if (isQueryLoading) {
      return /* @__PURE__ */ jsxRuntime.jsx("div", { className: "flex items-center justify-center p-12", children: /* @__PURE__ */ jsxRuntime.jsxs("div", { className: "flex flex-col items-center gap-3", children: [
        /* @__PURE__ */ jsxRuntime.jsx("div", { className: "animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500" }),
        /* @__PURE__ */ jsxRuntime.jsx("span", { className: "text-gray-500 text-sm", children: "Loading device data..." })
      ] }) });
    }
    if (queryError) {
      return /* @__PURE__ */ jsxRuntime.jsx("div", { className: "p-6", children: /* @__PURE__ */ jsxRuntime.jsxs("div", { className: "bg-red-50 border border-red-200 rounded-lg p-4", children: [
        /* @__PURE__ */ jsxRuntime.jsx("h4", { className: "text-red-800 font-medium mb-1", children: "Error loading device" }),
        /* @__PURE__ */ jsxRuntime.jsx("p", { className: "text-red-600 text-sm", children: queryError.message })
      ] }) });
    }
    const deviceResponse = queryData;
    const device = (_c = (_b = (_a = deviceResponse == null ? void 0 : deviceResponse.InfraDevice) == null ? void 0 : _a.edges) == null ? void 0 : _b[0]) == null ? void 0 : _c.node;
    if (!device) {
      return /* @__PURE__ */ jsxRuntime.jsx("div", { className: "p-6", children: /* @__PURE__ */ jsxRuntime.jsx("div", { className: "bg-yellow-50 border border-yellow-200 rounded-lg p-4", children: /* @__PURE__ */ jsxRuntime.jsx("p", { className: "text-yellow-700", children: "No device data available" }) }) });
    }
    const handleInterfaceClick = (iface) => {
      navigate(`/objects/InfraInterface/${iface.id}`);
    };
    return /* @__PURE__ */ jsxRuntime.jsx("div", { className: "p-6", children: /* @__PURE__ */ jsxRuntime.jsx(DeviceVisualization, { device, onInterfaceClick: handleInterfaceClick }) });
  }
  const plugins = [
    { manifest, component: DeviceInfoPlugin },
    { manifest: manifest$1, component: QuickStatsPlugin }
  ];
  exports.default = DeviceInfoPlugin;
  exports.manifest = manifest;
  exports.plugins = plugins;
  Object.defineProperties(exports, { __esModule: { value: true }, [Symbol.toStringTag]: { value: "Module" } });
  return exports;
})({}, window.InfrahubRuntime.jsxRuntime, window.InfrahubRuntime.ReactRouter);
//# sourceMappingURL=index.js.map

// Register plugin(s) with Infrahub
(function() {
  if (!window.InfrahubRuntime) {
    console.error('[InfrahubPlugin] InfrahubRuntime not found. Plugin cannot load.');
    return;
  }
  window.InfrahubPlugins = window.InfrahubPlugins || {};
  var exported = typeof InfrahubPluginExport !== 'undefined' ? InfrahubPluginExport : {};
  if (exported.plugins) {
    exported.plugins.forEach(function(p) {
      window.InfrahubPlugins[p.manifest.id] = p;
      console.log('[InfrahubPlugin] Registered:', p.manifest.id);
    });
  } else if (exported.manifest && exported.default) {
    window.InfrahubPlugins[exported.manifest.id] = { manifest: exported.manifest, component: exported.default };
    console.log('[InfrahubPlugin] Registered:', exported.manifest.id);
  }
})();
