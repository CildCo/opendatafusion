"""Small message catalogue for errors raised before a handler runs.

Only the guards that every console page hits are translated; technical
errors keep their original text so logs and tests stay stable.
"""

MESSAGES = {
    "auth.missing_token": ("缺少登录令牌", "Missing bearer token"),
    "auth.invalid_token": ("登录已过期或无效", "Invalid or expired token"),
    "auth.inactive_user": ("账号无效或已停用", "Invalid or inactive user"),
    "auth.editor": ("需要编辑权限", "Editor role required"),
    "auth.approver": ("需要审批权限", "Approver role required"),
    "auth.admin": ("需要管理员权限", "Administrator role required"),
    "auth.revoked": ("会话已失效，请重新登录", "Session has been revoked"),
    "auth.bad_credentials": ("用户名或密码错误", "Bad credentials"),
    "auth.inactive": ("账号已停用", "User is inactive"),
    "auth.project_not_found": ("项目不存在", "Project not found"),
    "auth.not_member": ("不是该项目成员", "Not a project member"),
    "auth.bad_otp": ("一次性验证码无效", "Invalid or missing one-time code"),
    "auth.too_many_logins": ("登录尝试过于频繁，请稍后再试",
                             "Too many login attempts"),
}


def language(header) -> str:
    if not isinstance(header, str):
        return "en"
    for part in header.split(","):
        tag = part.split(";")[0].strip().lower()
        if tag.startswith("zh"):
            return "zh"
        if tag.startswith("en"):
            return "en"
    return "en"


def tr(header: str | None, key: str) -> str:
    zh, en = MESSAGES[key]
    return zh if language(header) == "zh" else en
