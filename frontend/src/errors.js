import { t } from "./i18n";

const RULES = [
  [/at least one active administrator/i, "err.lastAdmin"],
  [/deactivate your own/i, "err.selfDeactivate"],
  [/change your own role/i, "err.selfRole"],
  [/approval (required|token)/i, "err.approval"],
  [/not a project member|outside the project|cross-project/i, "err.notMember"],
  [/webhook host is not allowed/i, "err.webhookHost"],
  [/invalid content/i, "err.invalidContent"],
  [/interface (is )?not published/i, "err.unpublished"],
  [/password must|password does not/i, "err.weakPassword"],
  [/already exists|duplicate|unique constraint/i, "err.exists"],
  [/connection (failed|refused)|could not connect|timed out/i, "err.connection"],
  [/permission|forbidden|not allowed/i, "err.forbidden"],
  [/invalid token|session/i, "err.session"],
  [/not found/i, "err.notFound"],
];

export function localizeError(message) {
  if (!message) return message;
  for (const [pattern, key] of RULES) {
    if (pattern.test(message)) return t(key);
  }
  return message;
}
