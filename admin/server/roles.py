#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
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
import logging
from typing import Any

from api.common.exceptions import AdminException
from api.db.services.enterprise_service import (
    PERMISSION_ACTIONS,
    RESOURCE_TYPES,
    RoleService,
)
from api.db.services.user_service import UserService


def _role_payload(role) -> dict[str, Any]:
    payload = role.to_dict()
    payload["name"] = payload.get("role_name", "")
    return payload


class RoleMgr:
    @staticmethod
    def create_role(role_name: str, description: str = "") -> dict[str, Any]:
        try:
            RoleService.ensure_default_roles()
            role = RoleService.create_role(role_name, description)
            return _role_payload(role)
        except ValueError as e:
            raise AdminException(str(e), 400)
        except Exception as e:
            logging.exception("create_role failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def update_role_description(role_name: str, description: str) -> dict[str, Any]:
        try:
            role = RoleService.update_role_description(role_name, description)
            return _role_payload(role)
        except LookupError as e:
            raise AdminException(str(e), 404)
        except Exception as e:
            logging.exception("update_role_description failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def delete_role(role_name: str) -> dict[str, Any]:
        try:
            RoleService.delete_role(role_name)
            return {"deleted": role_name}
        except (LookupError, ValueError) as e:
            raise AdminException(str(e), 400)
        except Exception as e:
            logging.exception("delete_role failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def list_roles() -> dict[str, Any]:
        try:
            RoleService.ensure_default_roles()
            roles = [_role_payload(role) for role in RoleService.list_roles()]
            return {"roles": roles, "total": len(roles)}
        except Exception as e:
            logging.exception("list_roles failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def list_roles_with_permission() -> dict[str, Any]:
        try:
            RoleService.ensure_default_roles()
            roles = []
            for role in RoleService.list_roles():
                payload = _role_payload(role)
                payload["permissions"] = RoleService.get_role_permissions(role.id)
                roles.append(payload)
            return {"roles": roles, "total": len(roles)}
        except Exception as e:
            logging.exception("list_roles_with_permission failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def get_role_permission(role_name: str) -> dict[str, Any]:
        try:
            role = RoleService.get_role_by_name(role_name)
            if not role:
                raise AdminException(f"Role '{role_name}' not found", 404)
            return {
                "role": _role_payload(role),
                "permissions": RoleService.get_role_permissions(role.id),
            }
        except AdminException:
            raise
        except Exception as e:
            logging.exception("get_role_permission failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def grant_role_permission(role_name: str, actions: list, resource: str) -> dict[str, Any]:
        try:
            RoleService.grant_role_permission(role_name, actions, resource)
            return {"role_name": role_name, "resource": resource, "actions": actions}
        except (LookupError, ValueError) as e:
            raise AdminException(str(e), 400)
        except Exception as e:
            logging.exception("grant_role_permission failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def revoke_role_permission(role_name: str, actions: list, resource: str) -> dict[str, Any]:
        try:
            RoleService.revoke_role_permission(role_name, actions, resource)
            return {"role_name": role_name, "resource": resource, "actions": actions}
        except LookupError as e:
            raise AdminException(str(e), 404)
        except Exception as e:
            logging.exception("revoke_role_permission failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def apply_permission_map(role_name: str, permissions_map: dict, revoke: bool = False) -> dict[str, Any]:
        role = RoleService.get_role_by_name(role_name)
        if not role:
            raise AdminException(f"Role '{role_name}' not found", 404)
        current = RoleService.get_role_permissions(role.id)
        for resource, actions in (permissions_map or {}).items():
            if resource not in current:
                continue
            for action, enabled in (actions or {}).items():
                if action not in current[resource]:
                    continue
                current[resource][action] = not revoke and bool(enabled)
        RoleService.set_role_permissions(role.id, current)
        return {"role_name": role_name, "permissions": current}

    @staticmethod
    def update_user_role(user_name: str, role_name: str) -> dict[str, Any]:
        try:
            users = UserService.query_user_by_email(user_name)
            if not users:
                raise AdminException(f"User '{user_name}' not found", 404)
            if len(users) > 1:
                raise AdminException(f"Exist more than 1 user: {user_name}!", 400)
            RoleService.set_user_role(users[0].id, role_name)
            return {"username": user_name, "role_name": role_name}
        except AdminException:
            raise
        except (LookupError, ValueError) as e:
            raise AdminException(str(e), 400)
        except Exception as e:
            logging.exception("update_user_role failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def get_user_permission(user_name: str) -> dict[str, Any]:
        try:
            users = UserService.query_user_by_email(user_name)
            if not users:
                raise AdminException(f"User '{user_name}' not found", 404)
            user = users[0]
            role_ids = RoleService.get_user_role_ids(user.id)
            role_names = []
            if role_ids:
                from api.db.db_models import Role

                rows = Role.select(Role.role_name).where(Role.id.in_(role_ids), Role.status == "1")
                role_names = [row.role_name for row in rows]
            return {
                "user": {"id": user.id, "username": user.email, "role": role_names[0] if role_names else ""},
                "role_permissions": RoleService.get_user_permissions(user.id),
            }
        except AdminException:
            raise
        except Exception as e:
            logging.exception("get_user_permission failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def list_resources() -> dict[str, Any]:
        return {"resource_types": RESOURCE_TYPES, "permission_actions": PERMISSION_ACTIONS}
