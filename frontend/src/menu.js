import {
  Bell, CircleCheck, Coin, Collection, Connection, Cpu, DataLine, EditPen,
  Folder, Grid, Key, Monitor, Odometer, Promotion, Share, Switch,
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
    { path: "/datasets", key: "menu.datasets", icon: Collection },
    { path: "/dashboards", key: "menu.dashboards", icon: Odometer },
    { path: "/apps", key: "menu.apps", icon: Grid },
    { path: "/dependencies", key: "menu.dependencies", icon: Switch },
  ] },
  { key: "nav.governance", items: [
    { path: "/apis", key: "menu.apis", icon: Connection },
    { path: "/governance", key: "menu.governance", icon: Collection },
    { path: "/grants", key: "menu.grants", icon: Key },
    { path: "/webhooks", key: "menu.webhooks", icon: Promotion },
    { path: "/quality", key: "menu.quality", icon: CircleCheck },
    { path: "/alerts", key: "menu.alerts", icon: Bell },
    { path: "/changes", key: "menu.changes", icon: Switch },
    { path: "/tools", key: "menu.tools", icon: Connection },
  ] },
];

export const MENU_ITEMS = MENU_GROUPS.flatMap((g) => g.items);
