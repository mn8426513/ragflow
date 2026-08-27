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
from api.db import KbPermission
from api.db.services.enterprise_service import KnowledgebaseACLService, RoleService
from api.db.services.user_service import UserService


def user_has_permission(user_id: str, resource: str, action: str) -> bool:
    """Check enterprise role permission for a resource action.

    Superusers always pass. Users without an assigned enterprise role keep the
    legacy open behavior so existing deployments are not locked out before
    roles are provisioned.
    """
    user = UserService.filter_by_id(user_id)
    if user and getattr(user, "is_superuser", False):
        return True
    role_ids = RoleService.get_user_role_ids(user_id)
    if not role_ids:
        return True
    resource_permissions = RoleService.get_user_permissions(user_id).get(resource, {})
    if not resource_permissions.get("enable"):
        return False
    return bool(resource_permissions.get(action))


def can_read_dataset(user_id: str, dataset_id: str) -> bool:
    if user_has_permission(user_id, "dataset", "read"):
        return True
    return KnowledgebaseACLService.has_permission(dataset_id, user_id, KbPermission.READ.value)


def can_write_dataset(user_id: str, dataset_id: str) -> bool:
    if user_has_permission(user_id, "dataset", "write"):
        return True
    return KnowledgebaseACLService.has_permission(dataset_id, user_id, KbPermission.WRITE.value)


def can_manage_dataset(user_id: str, dataset_id: str) -> bool:
    if user_has_permission(user_id, "dataset", "share"):
        return True
    return KnowledgebaseACLService.has_permission(dataset_id, user_id, KbPermission.MANAGE.value)


def can_write_agent(user_id: str, agent_id: str) -> bool:
    from api.db.services.canvas_service import UserCanvasService

    if user_has_permission(user_id, "agent", "write"):
        return True
    ok, canvas = UserCanvasService.get_by_canvas_id(agent_id)
    return ok and canvas.get("user_id") == user_id


def can_share_agent(user_id: str, agent_id: str) -> bool:
    from api.db.services.canvas_service import UserCanvasService

    if user_has_permission(user_id, "agent", "share"):
        return True
    ok, canvas = UserCanvasService.get_by_canvas_id(agent_id)
    return ok and canvas.get("user_id") == user_id


def can_write_chat(user_id: str, chat_id: str) -> bool:
    from api.db.services.dialog_service import DialogService
    from common.constants import StatusEnum

    if user_has_permission(user_id, "chat", "write"):
        return True
    return bool(DialogService.query(tenant_id=user_id, id=chat_id, status=StatusEnum.VALID.value))


def can_write_search(user_id: str, search_id: str) -> bool:
    from api.db.services.search_service import SearchService

    if user_has_permission(user_id, "search", "write"):
        return True
    return SearchService.accessible4deletion(search_id, user_id)


def can_write_memory(user_id: str, memory_id: str) -> bool:
    from api.db.db_models import Memory

    if user_has_permission(user_id, "memory", "write"):
        return True
    return Memory.get_or_none(Memory.id == memory_id, Memory.tenant_id == user_id) is not None
