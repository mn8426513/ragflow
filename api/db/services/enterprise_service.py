#
#  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import json
import logging
from datetime import datetime
from typing import Any

from api.db import AclSubjectType, KbPermission, RoleType
from api.db.db_models import (
    AuditLog,
    DB,
    Department,
    KnowledgebaseACL,
    Role,
    RolePermission,
    SystemSettings,
    UserDepartment,
    UserRole,
    Whitelist,
)
from api.db.services.common_service import CommonService
from api.db.services.user_service import TenantService
from common.constants import StatusEnum
from common.misc_utils import get_uuid
from common.time_utils import current_timestamp, datetime_format

RESOURCE_TYPES = ["dataset", "chat", "agent", "search", "file", "team", "memory"]
PERMISSION_ACTIONS = ["enable", "read", "write", "share"]


def _insert_and_get(service_cls, **kwargs):
    """Insert a row and return the persisted model instance.

    ``CommonService.insert`` returns the row count, not the model, so services
    that need the inserted row query it back by its generated id.
    """
    obj_id = kwargs.get("id") or get_uuid()
    kwargs["id"] = obj_id
    service_cls.insert(**kwargs)
    return service_cls.get_or_none(id=obj_id)


class DepartmentService(CommonService):
    model = Department

    @classmethod
    @DB.connection_context()
    def get_active_all(cls) -> list[dict[str, Any]]:
        rows = cls.model.select().where(cls.model.status == StatusEnum.VALID.value).order_by(cls.model.create_time.asc())
        return [row.to_dict() for row in rows]

    @classmethod
    @DB.connection_context()
    def create_department(cls, name: str, created_by: str, parent_id: str | None = None, description: str = "") -> dict[str, Any]:
        name = (name or "").strip()
        if not name:
            raise ValueError("Department name is required")
        if len(name) > 128:
            raise ValueError("Department name is too long")
        if cls.get_or_none(name=name, status=StatusEnum.VALID.value):
            raise ValueError(f"Department '{name}' already exists")
        obj = _insert_and_get(
            cls,
            name=name,
            parent_id=parent_id or None,
            description=description or "",
            created_by=created_by,
        )
        return obj.to_dict()

    @classmethod
    @DB.connection_context()
    def update_department(cls, department_id: str, update_dict: dict[str, Any]) -> dict[str, Any]:
        obj = cls.get_or_none(id=department_id, status=StatusEnum.VALID.value)
        if not obj:
            raise LookupError(f"Department '{department_id}' not found")
        if "name" in update_dict:
            name = (update_dict.get("name") or "").strip()
            if not name:
                raise ValueError("Department name is required")
            dup = cls.get_or_none(name=name, status=StatusEnum.VALID.value)
            if dup and dup.id != department_id:
                raise ValueError(f"Department '{name}' already exists")
            update_dict["name"] = name
        allowed = {"name", "parent_id", "description"}
        update_dict = {k: v for k, v in update_dict.items() if k in allowed}
        if update_dict:
            update_dict["update_time"] = current_timestamp()
            update_dict["update_date"] = datetime_format(datetime.now())
            cls.model.update(update_dict).where(cls.model.id == department_id).execute()
        return cls.get_or_none(id=department_id).to_dict()

    @classmethod
    @DB.connection_context()
    def delete_department(cls, department_id: str) -> None:
        children = cls.model.select(cls.model.id).where(cls.model.parent_id == department_id, cls.model.status == StatusEnum.VALID.value).count()
        if children:
            raise ValueError("Department has child departments, please remove them first")
        cls.model.update({"status": StatusEnum.INVALID.value, "update_time": current_timestamp(), "update_date": datetime_format(datetime.now())}).where(cls.model.id == department_id).execute()
        UserDepartment.delete().where(UserDepartment.department_id == department_id).execute()

    @classmethod
    @DB.connection_context()
    def get_department_ids_by_user(cls, user_id: str) -> list[str]:
        rows = UserDepartment.select(UserDepartment.department_id).where(
            UserDepartment.user_id == user_id,
            UserDepartment.status == StatusEnum.VALID.value,
        )
        return [row.department_id for row in rows]

    @classmethod
    @DB.connection_context()
    def list_members(cls, department_id: str) -> list[dict[str, Any]]:
        from api.db.db_models import User

        rows = (
            UserDepartment.select(UserDepartment.user_id, User.email, User.nickname)
            .join(User, on=(UserDepartment.user_id == User.id))
            .where(UserDepartment.department_id == department_id, UserDepartment.status == StatusEnum.VALID.value)
            .order_by(User.email.asc())
            .dicts()
        )
        return list(rows)

    @classmethod
    @DB.connection_context()
    def add_members(cls, department_id: str, user_ids: list[str]) -> None:
        if not cls.get_or_none(id=department_id, status=StatusEnum.VALID.value):
            raise LookupError(f"Department '{department_id}' not found")
        with DB.atomic():
            for user_id in user_ids:
                exists = UserDepartment.select().where(
                    UserDepartment.user_id == user_id,
                    UserDepartment.department_id == department_id,
                ).first()
                if exists:
                    if exists.status != StatusEnum.VALID.value:
                        UserDepartment.update({"status": StatusEnum.VALID.value, "update_time": current_timestamp(), "update_date": datetime_format(datetime.now())}).where(UserDepartment.id == exists.id).execute()
                    continue
                UserDepartment.insert(user_id=user_id, department_id=department_id)

    @classmethod
    @DB.connection_context()
    def remove_members(cls, department_id: str, user_ids: list[str]) -> None:
        UserDepartment.delete().where(
            UserDepartment.department_id == department_id,
            UserDepartment.user_id.in_(user_ids),
        ).execute()


class RoleService(CommonService):
    model = Role

    @classmethod
    @DB.connection_context()
    def ensure_default_roles(cls) -> None:
        defaults = [
            ("admin", "Built-in administrator role", ["dataset", "chat", "agent", "search", "file", "team", "memory"]),
            ("user", "Built-in regular user role", ["dataset", "chat", "agent", "search", "file"]),
        ]
        for name, description, resources in defaults:
            role = cls.get_or_none(role_name=name)
            if not role:
                role = _insert_and_get(cls, role_name=name, description=description, role_type=RoleType.BUILTIN.value)
            if not RolePermission.select().where(RolePermission.role_id == role.id).count():
                actions = ["enable", "read", "write", "share"] if name == "admin" else ["enable", "read"]
                rows = [
                    {"role_id": role.id, "resource": resource, "action": action}
                    for resource in resources
                    for action in actions
                ]
                logging.info(f"=========rows{rows}")
                for row in rows:
                    if not RolePermission.get_or_none(**row):
                        logging.info(f"=========singleRow{row}")
                        RolePermission.insert(**row)

    @classmethod
    @DB.connection_context()
    def list_roles(cls) -> list[dict[str, Any]]:
        rows = cls.model.select().where(cls.model.status == StatusEnum.VALID.value).order_by(cls.model.create_time.asc())
        return [row.to_dict() for row in rows]

    @classmethod
    @DB.connection_context()
    def create_role(cls, role_name: str, description: str = "") -> dict[str, Any]:
        role_name = (role_name or "").strip()
        if not role_name:
            raise ValueError("Role name is required")
        if cls.get_or_none(role_name=role_name, status=StatusEnum.VALID.value):
            raise ValueError(f"Role '{role_name}' already exists")
        role = _insert_and_get(cls, role_name=role_name, description=description or "", role_type=RoleType.CUSTOM.value)
        return role.to_dict()

    @classmethod
    @DB.connection_context()
    def update_role_description(cls, role_name: str, description: str) -> dict[str, Any]:
        role = cls.get_or_none(role_name=role_name, status=StatusEnum.VALID.value)
        if not role:
            raise LookupError(f"Role '{role_name}' not found")
        cls.model.update(
            {"description": description or "", "update_time": current_timestamp(), "update_date": datetime_format(datetime.now())}
        ).where(cls.model.id == role.id).execute()
        return cls.get_or_none(id=role.id).to_dict()

    @classmethod
    @DB.connection_context()
    def delete_role(cls, role_name: str) -> None:
        role = cls.get_or_none(role_name=role_name, status=StatusEnum.VALID.value)
        if not role:
            raise LookupError(f"Role '{role_name}' not found")
        if role.role_type == RoleType.BUILTIN.value:
            raise ValueError(f"Built-in role '{role_name}' cannot be deleted")
        with DB.atomic():
            RolePermission.delete().where(RolePermission.role_id == role.id).execute()
            UserRole.delete().where(UserRole.role_id == role.id).execute()
            cls.model.update({"status": StatusEnum.INVALID.value, "update_time": current_timestamp(), "update_date": datetime_format(datetime.now())}).where(cls.model.id == role.id).execute()

    @classmethod
    @DB.connection_context()
    def get_role_by_name(cls, role_name: str):
        return cls.get_or_none(role_name=role_name, status=StatusEnum.VALID.value)

    @classmethod
    @DB.connection_context()
    def get_role_permissions(cls, role_id: str) -> dict[str, dict[str, bool]]:
        rows = (
            RolePermission.select()
            .where(RolePermission.role_id == role_id, RolePermission.status == StatusEnum.VALID.value)
        )
        result = {resource: {action: False for action in PERMISSION_ACTIONS} for resource in RESOURCE_TYPES}
        for row in rows:
            result.setdefault(row.resource, {action: False for action in PERMISSION_ACTIONS})[row.action] = True
        return result

    @classmethod
    @DB.connection_context()
    def set_role_permissions(cls, role_id: str, permissions: dict[str, dict[str, bool]]) -> None:
        role = cls.get_or_none(id=role_id, status=StatusEnum.VALID.value)
        if not role:
            raise LookupError("Role not found")
        with DB.atomic():
            RolePermission.delete().where(RolePermission.role_id == role_id).execute()
            for resource, actions in (permissions or {}).items():
                if resource not in RESOURCE_TYPES:
                    continue
                for action, enabled in (actions or {}).items():
                    if action not in PERMISSION_ACTIONS or not enabled:
                        continue
                    RolePermission.insert(role_id=role_id, resource=resource, action=action)

    @classmethod
    @DB.connection_context()
    def grant_role_permission(cls, role_name: str, actions: list[str], resource: str) -> None:
        role = cls.get_or_none(role_name=role_name, status=StatusEnum.VALID.value)
        if not role:
            raise LookupError(f"Role '{role_name}' not found")
        if resource not in RESOURCE_TYPES:
            raise ValueError(f"Unsupported resource '{resource}'")
        for action in actions:
            if action not in PERMISSION_ACTIONS:
                continue
            if not RolePermission.get_or_none(role_id=role.id, resource=resource, action=action, status=StatusEnum.VALID.value):
                RolePermission.insert(role_id=role.id, resource=resource, action=action)

    @classmethod
    @DB.connection_context()
    def revoke_role_permission(cls, role_name: str, actions: list[str], resource: str) -> None:
        role = cls.get_or_none(role_name=role_name, status=StatusEnum.VALID.value)
        if not role:
            raise LookupError(f"Role '{role_name}' not found")
        RolePermission.delete().where(
            RolePermission.role_id == role.id,
            RolePermission.resource == resource,
            RolePermission.action.in_(actions),
        ).execute()

    @classmethod
    @DB.connection_context()
    def get_user_role_ids(cls, user_id: str) -> list[str]:
        return [row.role_id for row in UserRole.select(UserRole.role_id).where(UserRole.user_id == user_id, UserRole.status == StatusEnum.VALID.value)]

    @classmethod
    @DB.connection_context()
    def set_user_role(cls, user_id: str, role_name: str) -> None:
        role = cls.get_or_none(role_name=role_name, status=StatusEnum.VALID.value)
        if not role:
            raise LookupError(f"Role '{role_name}' not found")
        with DB.atomic():
            UserRole.delete().where(UserRole.user_id == user_id).execute()
            UserRole.insert(user_id=user_id, role_id=role.id)

    @classmethod
    @DB.connection_context()
    def get_user_permissions(cls, user_id: str) -> dict[str, dict[str, bool]]:
        result = {resource: {action: False for action in PERMISSION_ACTIONS} for resource in RESOURCE_TYPES}
        role_ids = cls.get_user_role_ids(user_id)
        if not role_ids:
            default_role = cls.get_or_none(role_name="user", status=StatusEnum.VALID.value)
            if default_role:
                role_ids = [default_role.id]
        if role_ids:
            rows = RolePermission.select().where(RolePermission.role_id.in_(role_ids), RolePermission.status == StatusEnum.VALID.value)
            for row in rows:
                result.setdefault(row.resource, {action: False for action in PERMISSION_ACTIONS})[row.action] = True
        return result


class KnowledgebaseACLService(CommonService):
    model = KnowledgebaseACL

    @classmethod
    @DB.connection_context()
    def list_acl(cls, kb_id: str) -> list[dict[str, Any]]:
        rows = cls.model.select().where(cls.model.kb_id == kb_id, cls.model.status == StatusEnum.VALID.value).order_by(cls.model.create_time.asc())
        return [row.to_dict() for row in rows]

    @classmethod
    @DB.connection_context()
    def replace_acl(cls, kb_id: str, grants: list[dict[str, Any]], created_by: str) -> None:
        with DB.atomic():
            cls.model.delete().where(cls.model.kb_id == kb_id).execute()
            for grant in grants or []:
                subject_type = str(grant.get("subject_type", "")).strip().lower()
                subject_id = str(grant.get("subject_id", "")).strip()
                permission = str(grant.get("permission", "")).strip().lower()
                if subject_type not in {item.value for item in AclSubjectType}:
                    raise ValueError(f"Unsupported subject_type '{subject_type}'")
                if permission not in {item.value for item in KbPermission}:
                    raise ValueError(f"Unsupported permission '{permission}'")
                if not subject_id:
                    continue
                cls.model.insert(kb_id=kb_id, subject_type=subject_type, subject_id=subject_id, permission=permission, created_by=created_by)

    @classmethod
    @DB.connection_context()
    def get_user_subject_ids(cls, user_id: str) -> list[tuple[str, str]]:
        subjects = [(AclSubjectType.USER.value, user_id)]
        subjects.extend((AclSubjectType.DEPARTMENT.value, dept_id) for dept_id in DepartmentService.get_department_ids_by_user(user_id))
        subjects.extend((AclSubjectType.ROLE.value, role_id) for role_id in RoleService.get_user_role_ids(user_id))
        joined = TenantService.get_joined_tenants_by_user_id(user_id)
        subjects.extend((AclSubjectType.TEAM.value, tenant["tenant_id"]) for tenant in joined)
        return subjects

    @classmethod
    @DB.connection_context()
    def accessible_kb_ids(cls, user_id: str) -> set[str]:
        subjects = cls.get_user_subject_ids(user_id)
        if not subjects:
            return set()
        condition = None
        for subject_type, subject_id in subjects:
            clause = (cls.model.subject_type == subject_type) & (cls.model.subject_id == subject_id)
            condition = clause if condition is None else (condition | clause)
        rows = cls.model.select(cls.model.kb_id).where(condition, cls.model.status == StatusEnum.VALID.value)
        return {row.kb_id for row in rows}

    @classmethod
    @DB.connection_context()
    def has_permission(cls, kb_id: str, user_id: str, permission: str) -> bool:
        from api.db.db_models import Knowledgebase
        from api.db.services.user_service import UserService as _UserService

        user = _UserService.filter_by_id(user_id)
        if user and getattr(user, "is_superuser", False):
            return True
        kb = Knowledgebase.get_or_none(Knowledgebase.id == kb_id, Knowledgebase.status == StatusEnum.VALID.value)
        if not kb:
            return False
        if kb.tenant_id == user_id or kb.created_by == user_id:
            return True
        if permission == KbPermission.READ.value and kb.permission == "team":
            joined = TenantService.get_joined_tenants_by_user_id(user_id)
            if any(tenant["tenant_id"] == kb.tenant_id for tenant in joined):
                return True
        allowed = {KbPermission.READ.value, KbPermission.WRITE.value, KbPermission.MANAGE.value}
        if permission not in allowed:
            return False
        hierarchy = {
            KbPermission.READ.value: 0,
            KbPermission.WRITE.value: 1,
            KbPermission.MANAGE.value: 2,
        }
        required_level = hierarchy[permission]
        required = {item.value for item in KbPermission if hierarchy[item.value] >= required_level}
        subjects = cls.get_user_subject_ids(user_id)
        if not subjects:
            return False
        condition = None
        for subject_type, subject_id in subjects:
            clause = (cls.model.subject_type == subject_type) & (cls.model.subject_id == subject_id)
            condition = clause if condition is None else (condition | clause)
        rows = cls.model.select(cls.model.permission).where(
            condition,
            cls.model.kb_id == kb_id,
            cls.model.status == StatusEnum.VALID.value,
            cls.model.permission.in_(list(required)),
        )
        return rows.count() > 0


class AuditLogService(CommonService):
    model = AuditLog

    @classmethod
    @DB.connection_context()
    def record(cls, user_id: str, email: str, action: str, resource_type: str = "", resource_id: str = "", detail: str = "", ip_address: str = "", user_agent: str = "") -> None:
        try:
            cls.insert(
                user_id=user_id,
                email=email,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                detail=detail[:4000] if detail else "",
                ip_address=ip_address,
                user_agent=user_agent[:500] if user_agent else "",
            )
        except Exception as e:  # noqa: BLE001
            logging.exception("Failed to record audit log: %s", e)

    @classmethod
    @DB.connection_context()
    def list_logs(cls, page: int = 1, page_size: int = 20, email: str = "", action: str = "", resource_type: str = "") -> tuple[list[dict[str, Any]], int]:
        query = cls.model.select().where(cls.model.status == StatusEnum.VALID.value)
        if email:
            query = query.where(cls.model.email.contains(email))
        if action:
            query = query.where(cls.model.action.contains(action))
        if resource_type:
            query = query.where(cls.model.resource_type == resource_type)
        total = query.count()
        rows = query.order_by(cls.model.create_time.desc()).paginate(max(1, page), max(1, min(page_size, 200)))
        return [row.to_dict() for row in rows], total


class WhitelistService(CommonService):
    model = Whitelist

    @classmethod
    @DB.connection_context()
    def list_whitelist(cls) -> list[dict[str, Any]]:
        rows = cls.model.select().where(cls.model.status == StatusEnum.VALID.value).order_by(cls.model.create_time.desc())
        return [row.to_dict() for row in rows]

    @classmethod
    @DB.connection_context()
    def is_registration_allowed(cls, email: str) -> bool:
        email = (email or "").strip().lower()
        rows = cls.model.select(cls.model.email).where(cls.model.status == StatusEnum.VALID.value)
        allowed = [row.email for row in rows]
        if not allowed:
            return True
        return email in allowed

    @classmethod
    @DB.connection_context()
    def add_email(cls, email: str, created_by: str) -> dict[str, Any]:
        email = (email or "").strip().lower()
        if not email or "@" not in email:
            raise ValueError("A valid email is required")
        existing = cls.get_or_none(email=email)
        if existing:
            if existing.status == StatusEnum.INVALID.value:
                cls.model.update({"status": StatusEnum.VALID.value, "update_time": current_timestamp(), "update_date": datetime_format(datetime.now())}).where(cls.model.id == existing.id).execute()
            return cls.get_or_none(id=existing.id).to_dict()
        obj = Whitelist.create(email=email, created_by=created_by)
        return obj.to_dict()

    @classmethod
    @DB.connection_context()
    def update_email(cls, whitelist_id: int | str, email: str) -> dict[str, Any]:
        email = (email or "").strip().lower()
        if not email or "@" not in email:
            raise ValueError("A valid email is required")
        cls.model.update({"email": email, "update_time": current_timestamp(), "update_date": datetime_format(datetime.now())}).where(cls.model.id == whitelist_id).execute()
        return cls.get_or_none(id=whitelist_id).to_dict()

    @classmethod
    @DB.connection_context()
    def delete_email(cls, email: str) -> None:
        cls.model.update({"status": StatusEnum.INVALID.value, "update_time": current_timestamp(), "update_date": datetime_format(datetime.now())}).where(cls.model.email == (email or "").strip().lower()).execute()

    @classmethod
    @DB.connection_context()
    def batch_add(cls, emails: list[str], created_by: str, overwrite: bool = False) -> int:
        added = 0
        for email in emails:
            try:
                cls.add_email(email, created_by)
                added += 1
            except Exception:
                continue
        return added


@DB.connection_context()
def _get_setting_json(name: str, default: Any) -> Any:
    rows = SystemSettings.select().where(SystemSettings.name == name)
    if not rows:
        return default
    try:
        return json.loads(rows[0].value or "null")
    except Exception:
        return default


@DB.connection_context()
def _set_setting_json(name: str, value: Any, source: str = "enterprise") -> None:
    payload = json.dumps(value, ensure_ascii=False)
    row = SystemSettings.get_or_none(SystemSettings.name == name)
    if row:
        SystemSettings.update({"value": payload, "update_time": current_timestamp(), "update_date": datetime_format(datetime.now())}).where(SystemSettings.name == name).execute()
    else:
        SystemSettings.insert(name=name, source=source, data_type="json", value=payload, create_time=current_timestamp(), create_date=datetime_format(datetime.now()), update_time=current_timestamp(), update_date=datetime_format(datetime.now()))


def get_security_settings() -> dict[str, Any]:
    default = {
        "password_policy": {
            "min_length": 8,
            "require_uppercase": False,
            "require_lowercase": False,
            "require_digit": False,
            "require_special": False,
        },
        "watermark": {
            "enabled": False,
            "text": "${user_email} ${user_name}",
            "opacity": 0.08,
            "font_size": 16,
        },
        "login_lockout": {"max_attempts": 5, "lock_minutes": 15},
        "session_timeout_minutes": 480,
    }
    settings = _get_setting_json("enterprise.security", default)
    if not isinstance(settings, dict):
        settings = default
    for key, fallback in default.items():
        if key not in settings:
            settings[key] = fallback
    return settings


def set_security_settings(patch: dict[str, Any]) -> dict[str, Any]:
    current = get_security_settings()
    for key, value in (patch or {}).items():
        if key in current and isinstance(current[key], dict) and isinstance(value, dict):
            current[key].update(value)
        else:
            current[key] = value
    _set_setting_json("enterprise.security", current)
    return current


def get_sso_providers() -> list[dict[str, Any]]:
    providers = _get_setting_json("enterprise.sso.providers", [])
    return providers if isinstance(providers, list) else []


def set_sso_providers(providers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = []
    for provider in providers or []:
        if not isinstance(provider, dict) or not provider.get("channel") or not provider.get("type"):
            continue
        item = {
            "channel": str(provider["channel"]).strip(),
            "type": str(provider["type"]).strip(),
            "display_name": str(provider.get("display_name") or provider["channel"]).strip(),
            "icon": str(provider.get("icon") or "sso").strip(),
            "client_id": str(provider.get("client_id") or "").strip(),
            "client_secret": str(provider.get("client_secret") or "").strip(),
            "redirect_uri": str(provider.get("redirect_uri") or "").strip(),
            "issuer": str(provider.get("issuer") or "").strip(),
            "authorization_url": str(provider.get("authorization_url") or "").strip(),
            "token_url": str(provider.get("token_url") or "").strip(),
            "userinfo_url": str(provider.get("userinfo_url") or "").strip(),
            "scope": str(provider.get("scope") or "openid email profile").strip(),
        }
        if item["type"] not in ("oauth2", "oidc", "github"):
            continue
        cleaned.append(item)
    _set_setting_json("enterprise.sso.providers", cleaned)
    return cleaned


def get_db_sso_providers() -> dict[str, dict[str, Any]]:
    return {provider["channel"]: provider for provider in get_sso_providers()}



def check_password_policy(password: str) -> tuple[bool, str]:
    policy = get_security_settings().get("password_policy", {})
    min_length = int(policy.get("min_length", 8) or 0)
    if len(password or "") < min_length:
        return False, f"Password must be at least {min_length} characters"
    if policy.get("require_uppercase") and not any(ch.isupper() for ch in password):
        return False, "Password must contain an uppercase letter"
    if policy.get("require_lowercase") and not any(ch.islower() for ch in password):
        return False, "Password must contain a lowercase letter"
    if policy.get("require_digit") and not any(ch.isdigit() for ch in password):
        return False, "Password must contain a digit"
    if policy.get("require_special") and not any(ch in "!@#$%^&*()-_=+[]{};:,.<>?/~`" for ch in password):
        return False, "Password must contain a special character"
    return True, ""
