import {
  Bell, CircleCheck, Coin, Collection, Connection, Cpu, DataLine, Document,
  EditPen, Folder, Grid, Key, Lock, Monitor, Odometer, Promotion, Setting,
  Share, Switch, User,
} from "@element-plus/icons-vue";

export const MENU_GROUPS = [
  { key: "nav.workspace", items: [
    { path: "/dashboard", key: "menu.dashboard", icon: Odometer },
    { path: "/ops", key: "menu.ops", icon: Monitor },
  ] },
  { key: "nav.assets", items: [
    { path: "/datasources", key: "menu.datasources", icon: Coin },
    { path: "/catalog", key: "menu.catalog", icon: Collection },
    { path: "/workbench", key: "menu.workbench", icon: EditPen },
    { path: "/files", key: "menu.files", icon: Folder },
  ] },
  { key: "nav.development", items: [
    { path: "/pipelines", key: "menu.pipelines", icon: Share },
    { path: "/engines", key: "menu.engines", icon: Cpu },
    { path: "/cdc", key: "menu.cdc", icon: DataLine },
    { path: "/flows", key: "menu.flows", icon: Share },
    { path: "/datasets", key: "menu.datasets", icon: Collection },
    { path: "/dashboards", key: "menu.dashboards", icon: Odometer },
    { path: "/apps", key: "menu.apps", icon: Grid },
  ] },
  { key: "nav.governance", items: [
    { path: "/apis", key: "menu.apis", icon: Connection },
    { path: "/interfaces", key: "menu.interfaces", icon: Connection },
    { path: "/grants", key: "menu.grants", icon: Key },
    { path: "/webhooks", key: "menu.webhooks", icon: Promotion },
    { path: "/quality", key: "menu.quality", icon: CircleCheck },
    { path: "/alerts", key: "menu.alerts", icon: Bell },
    { path: "/changes", key: "menu.changes", icon: Switch },
    { path: "/tools", key: "menu.tools", icon: Connection },
  ] },
  { key: "nav.management", items: [
    { path: "/users", key: "menu.users", icon: User, adminOnly: true },
    { path: "/workspace", key: "menu.workspace", icon: Setting },
    { path: "/security", key: "menu.security", icon: Lock },
    { path: "/audit", key: "menu.audit", icon: Document, adminOnly: true },
  ] },
];

export const MENU_ITEMS = MENU_GROUPS.flatMap((g) => g.items);
