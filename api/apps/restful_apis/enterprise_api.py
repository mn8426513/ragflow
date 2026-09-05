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

from quart import request

from api.apps import current_user, login_required
from api.db import KbPermission
from api.db.db_models import User
from api.db.services.enterprise_service import (
    AuditLogService,
    DepartmentService,
    KnowledgebaseACLService,
    RoleService,
    get_security_settings,
)
from api.utils.api_utils import get_error_data_result, get_json_result
from common.constants import RetCode, StatusEnum


@manager.route("/enterprise/access/targets", methods=["GET"])  # noqa: F821
@login_required
async def list_access_targets():
    """Return departments, roles and users available for fine-grained grants."""
    try:
        departments = [
            {"id": item["id"], "name": item["name"], "parent_id": item.get("parent_id")}
            for item in DepartmentService.get_active_all()
        ]
        roles = [
            {"id": item["id"], "role_name": item["role_name"]}
            for item in RoleService.list_roles()
        ]
        users = list(
            User.select(User.id, User.email, User.nickname)
            .where(User.status == StatusEnum.VALID.value)
            .order_by(User.email.asc())
            .dicts()
        )
        return get_json_result(data={"departments": departments, "roles": roles, "users": users})
    except Exception as e:
        logging.exception("list access targets failed")
        return get_error_data_result(message=str(e))


@manager.route("/enterprise/datasets/<dataset_id>/permissions", methods=["GET"])  # noqa: F821
@login_required
async def get_dataset_permissions(dataset_id: str):
    """Get fine-grained permission entries for a dataset."""
    try:
        if not KnowledgebaseACLService.has_permission(dataset_id, current_user.id, KbPermission.MANAGE.value):
            return get_json_result(data=False, code=RetCode.OPERATING_ERROR, message="Only the owner or a manager can view dataset permissions.")
        grants = KnowledgebaseACLService.list_acl(dataset_id)
        return get_json_result(data={"grants": grants})
    except Exception as e:
        logging.exception("get dataset permissions failed")
        return get_error_data_result(message=str(e))


@manager.route("/enterprise/datasets/<dataset_id>/permissions", methods=["PUT"])  # noqa: F821
@login_required
async def update_dataset_permissions(dataset_id: str):
    """Replace all fine-grained permission entries for a dataset."""
    try:
        if not KnowledgebaseACLService.has_permission(dataset_id, current_user.id, KbPermission.MANAGE.value):
            return get_json_result(data=False, code=RetCode.OPERATING_ERROR, message="Only the owner or a manager can modify dataset permissions.")
        payload = await request.get_json()
        if not isinstance(payload, dict):
            return get_error_data_result(message="Invalid request body")
        grants = payload.get("grants", [])
        if not isinstance(grants, list):
            return get_error_data_result(message="grants must be a list")
        KnowledgebaseACLService.replace_acl(dataset_id, grants, current_user.id)
        AuditLogService.record(
            user_id=current_user.id,
            email=current_user.email,
            action="update dataset permissions",
            resource_type="dataset",
            resource_id=dataset_id,
            ip_address=request.remote_addr or "",
            user_agent=request.headers.get("User-Agent", ""),
        )
        return get_json_result(data=True)
    except ValueError as e:
        return get_error_data_result(message=str(e))
    except Exception as e:
        logging.exception("update dataset permissions failed")
        return get_error_data_result(message=str(e))


@manager.route("/enterprise/security/watermark", methods=["GET"])  # noqa: F821
@login_required
async def get_watermark_config():
    """Return the current watermark policy for the browser overlay."""
    try:
        security = get_security_settings()
        return get_json_result(data=security.get("watermark", {}))
    except Exception as e:
        logging.exception("get watermark config failed")
        return get_error_data_result(message=str(e))
