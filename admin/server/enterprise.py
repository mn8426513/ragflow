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
import logging
from typing import Any

from api.common.exceptions import AdminException
from api.db.services.enterprise_service import (
    AuditLogService,
    DepartmentService,
    WhitelistService,
    get_security_settings,
    get_sso_providers,
    set_security_settings,
    set_sso_providers,
)
from api.db.services.user_service import UserService


class DepartmentMgr:
    @staticmethod
    def list_departments() -> dict[str, Any]:
        try:
            departments = DepartmentService.get_active_all()
            return {"departments": departments, "total": len(departments)}
        except Exception as e:
            logging.exception("list_departments failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def create_department(operator: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            department = DepartmentService.create_department(
                name=payload.get("name", ""),
                created_by=operator,
                parent_id=payload.get("parent_id"),
                description=payload.get("description", ""),
            )
            return department
        except ValueError as e:
            raise AdminException(str(e), 400)
        except Exception as e:
            logging.exception("create_department failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def update_department(department_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return DepartmentService.update_department(department_id, payload)
        except LookupError as e:
            raise AdminException(str(e), 404)
        except ValueError as e:
            raise AdminException(str(e), 400)
        except Exception as e:
            logging.exception("update_department failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def delete_department(department_id: str) -> dict[str, Any]:
        try:
            DepartmentService.delete_department(department_id)
            return {"deleted": department_id}
        except ValueError as e:
            raise AdminException(str(e), 400)
        except Exception as e:
            logging.exception("delete_department failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def list_members(department_id: str) -> dict[str, Any]:
        try:
            members = DepartmentService.list_members(department_id)
            return {"members": members, "total": len(members)}
        except Exception as e:
            logging.exception("list department members failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def add_members(department_id: str, user_ids: list[str]) -> dict[str, Any]:
        try:
            DepartmentService.add_members(department_id, user_ids)
            return {"department_id": department_id, "user_ids": user_ids}
        except LookupError as e:
            raise AdminException(str(e), 404)
        except Exception as e:
            logging.exception("add department members failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def remove_members(department_id: str, user_ids: list[str]) -> dict[str, Any]:
        try:
            DepartmentService.remove_members(department_id, user_ids)
            return {"department_id": department_id, "user_ids": user_ids}
        except Exception as e:
            logging.exception("remove department members failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def get_user_department(user_name: str) -> dict[str, Any]:
        users = UserService.query_user_by_email(user_name)
        if not users:
            raise AdminException(f"User '{user_name}' not found", 404)
        dept_ids = DepartmentService.get_department_ids_by_user(users[0].id)
        departments = [d for d in DepartmentService.get_active_all() if d["id"] in dept_ids]
        return {"departments": departments}

    @staticmethod
    def set_user_department(user_name: str, department_id: str) -> dict[str, Any]:
        users = UserService.query_user_by_email(user_name)
        if not users:
            raise AdminException(f"User '{user_name}' not found", 404)
        from api.db.db_models import UserDepartment

        UserDepartment.delete().where(UserDepartment.user_id == users[0].id).execute()
        if department_id:
            DepartmentService.add_members(department_id, [users[0].id])
        return {"username": user_name, "department_id": department_id or ""}


class AuditMgr:
    @staticmethod
    def list_logs(page: int, page_size: int, email: str, action: str, resource_type: str) -> dict[str, Any]:
        try:
            logs, total = AuditLogService.list_logs(page, page_size, email, action, resource_type)
            return {"logs": logs, "total": total}
        except Exception as e:
            logging.exception("list audit logs failed")
            raise AdminException(str(e), 500)


class SecurityMgr:
    @staticmethod
    def get_settings() -> dict[str, Any]:
        try:
            return get_security_settings()
        except Exception as e:
            logging.exception("get security settings failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def update_settings(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return set_security_settings(payload)
        except Exception as e:
            logging.exception("update security settings failed")
            raise AdminException(str(e), 500)


class SsoMgr:
    @staticmethod
    def get_providers() -> dict[str, Any]:
        try:
            providers = get_sso_providers()
            masked = []
            for provider in providers:
                item = dict(provider)
                if item.get("client_secret"):
                    item["client_secret"] = "********"
                masked.append(item)
            return {"providers": masked}
        except Exception as e:
            logging.exception("get sso providers failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def update_providers(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            providers = set_sso_providers(payload.get("providers", []))
            return {"providers": providers}
        except Exception as e:
            logging.exception("update sso providers failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def test_provider(payload: dict[str, Any]) -> dict[str, Any]:
        provider_type = str(payload.get("type", "")).lower()
        issuer = str(payload.get("issuer") or "").strip()
        if provider_type == "oidc":
            if not issuer:
                raise AdminException("issuer is required for OIDC", 400)
            try:
                from common.http_client import sync_request

                metadata_url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
                response = sync_request("GET", metadata_url, timeout=7)
                response.raise_for_status()
                metadata = response.json()
                return {
                    "ok": True,
                    "issuer": metadata.get("issuer"),
                    "authorization_endpoint": metadata.get("authorization_endpoint"),
                    "token_endpoint": metadata.get("token_endpoint"),
                    "userinfo_endpoint": metadata.get("userinfo_endpoint"),
                }
            except Exception as e:
                raise AdminException(f"OIDC discovery failed: {e}", 400)
        required = ["authorization_url", "token_url", "userinfo_url"]
        missing = [key for key in required if not str(payload.get(key) or "").strip()]
        if missing:
            raise AdminException(f"Missing OAuth2 endpoints: {', '.join(missing)}", 400)
        return {"ok": True, "type": provider_type}


class WhitelistMgr:
    @staticmethod
    def list_whitelist() -> dict[str, Any]:
        try:
            items = WhitelistService.list_whitelist()
            return {"white_list": items, "total": len(items)}
        except Exception as e:
            logging.exception("list whitelist failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def add_email(operator: str, email: str) -> dict[str, Any]:
        try:
            return WhitelistService.add_email(email, operator)
        except ValueError as e:
            raise AdminException(str(e), 400)
        except Exception as e:
            logging.exception("add whitelist email failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def update_email(whitelist_id: str, email: str) -> dict[str, Any]:
        try:
            return WhitelistService.update_email(whitelist_id, email)
        except ValueError as e:
            raise AdminException(str(e), 400)
        except Exception as e:
            logging.exception("update whitelist email failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def delete_email(email: str) -> dict[str, Any]:
        try:
            WhitelistService.delete_email(email)
            return {"deleted": email}
        except Exception as e:
            logging.exception("delete whitelist email failed")
            raise AdminException(str(e), 500)

    @staticmethod
    def batch_add(operator: str, emails: list[str]) -> dict[str, Any]:
        try:
            added = WhitelistService.batch_add(emails, operator)
            return {"added": added}
        except Exception as e:
            logging.exception("batch add whitelist failed")
            raise AdminException(str(e), 500)
