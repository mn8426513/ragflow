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
from common.misc_utils import get_uuid
from api.db.db_models import DB, TenantModelProvider, TenantModelInstance, TenantModel
from api.db.services.common_service import CommonService


class TenantModelProviderService(CommonService):
    """租户模型提供商服务 (Tenant Model Provider Service)"""
    model = TenantModelProvider

    @classmethod
    @DB.connection_context()
    def get_by_tenant_id_and_provider_name(cls, tenant_id, provider_name):
        """根据租户ID和提供商名称获取提供商记录"""
        return cls.model.get_or_none(
            cls.model.tenant_id == tenant_id,
            cls.model.provider_name == provider_name,
        )

    @classmethod
    @DB.connection_context()
    def get_by_tenant_id_and_provider_id(cls, tenant_id, provider_id):
        return cls.model.get_or_none(
            cls.model.tenant_id == tenant_id,
            cls.model.id == provider_id,
        )

    @classmethod
    @DB.connection_context()
    def get_by_tenant_id(cls, tenant_id):
        """获取指定租户的所有模型提供商"""
        return list(cls.model.select().where(cls.model.tenant_id == tenant_id))

    @classmethod
    @DB.connection_context()
    def delete_by_tenant_id(cls, tenant_id):
        """删除指定租户的所有模型提供商"""
        return cls.model.delete().where(cls.model.tenant_id == tenant_id).execute()

    @classmethod
    @DB.connection_context()
    def delete_by_tenant_id_and_provider_name(cls, tenant_id, provider_name):
        return (
            cls.model.delete()
            .where(
                cls.model.tenant_id == tenant_id,
                cls.model.provider_name == provider_name,
            )
            .execute()
        )

    @classmethod
    @DB.connection_context()
    def list_provider_names_by_tenant_id(cls, tenant_id):
        """列出指定租户的所有提供商名称"""
        return [row.provider_name for row in cls.model.select(cls.model.provider_name).where(cls.model.tenant_id == tenant_id)]


    @classmethod
    @DB.connection_context()
    def list_providers_by_tenant_id_and_create_user_id(cls, tenant_id, create_user_id):
        """根据租户ID和创建用户ID查询提供商列表 (Query providers by tenant_id and create_user_id)"""
        fields = [cls.model.id, cls.model.create_time, cls.model.create_date, cls.model.update_time, cls.model.update_date,
                  cls.model.provider_name, cls.model.tenant_id, cls.model.create_user_id]
        return list(cls.model.select().where(
            cls.model.tenant_id == tenant_id, cls.model.create_user_id == create_user_id).dicts())

    @classmethod
    @DB.connection_context()
    def sync_providers_to_user(cls, tenant_id, from_user_id, to_user_id):
        """将邀请人的模型提供商、实例和模型同步给被邀请用户

        当团队 owner 邀请新成员加入团队时，将 owner 配置的模型提供商 (TenantModelProvider)、
        模型实例 (TenantModelInstance) 和模型 (TenantModel) 复制一份给被邀请用户。

        Args:
            tenant_id: 租户ID (团队ID)
            from_user_id: 邀请人的用户ID (模型来源)
            to_user_id: 被邀请人的用户ID (模型目标)

        Returns:
            dict: 包含复制统计信息的字典 {"providers": int, "instances": int, "models": int}
        """
        result = {"providers": 0, "instances": 0, "models": 0}

        # 第一步: 获取邀请人的所有模型提供商 (Step 1: Get all providers of the inviter)
        source_providers = cls.list_providers_by_tenant_id_and_create_user_id(tenant_id, from_user_id)
        if not source_providers:
            logging.info(f"No providers found for user {from_user_id} in tenant {tenant_id}")
            return result

        # old_provider_id → new_provider_id 映射表 (Mapping from old provider IDs to new provider IDs)
        provider_id_map = {}

        for src_provider in source_providers:
            provider_name = src_provider["provider_name"]
            provider_id = src_provider["id"]

            # 检查被邀请用户是否已存在同名提供商 (Check if the invited user already has this provider)
            # existing = cls.get_by_tenant_id_and_provider_name(to_user_id, provider_name)
            # 还需要检查是否原本就有了模型提供
            existing_for_user = TenantModelProvider.get_or_none(
                TenantModelProvider.tenant_id == to_user_id,
                TenantModelProvider.provider_name == provider_name,
                TenantModelProvider.create_user_id == tenant_id
            )
            if existing_for_user:
                logging.info(f"该团队的 Provider '{provider_name}' already exists for user {to_user_id}, skipping")
                provider_id_map[provider_id] = existing_for_user.id
                continue

            # 创建新的提供商记录 (Create new provider record for invited user)
            new_provider_id = get_uuid()
            cls.insert(
                id=new_provider_id,
                provider_name=provider_name,
                tenant_id=to_user_id,
                create_user_id=tenant_id,
            )
            provider_id_map[provider_id] = new_provider_id
            result["providers"] += 1
            logging.info(f"Copied provider '{provider_name}' ({provider_id} → {new_provider_id}) for user {to_user_id}")

        # 第二步: 复制模型实例 (Step 2: Copy model instances)
        src_provider_ids = [p["id"] for p in source_providers]
        if src_provider_ids:
            src_instances = list(TenantModelInstance.select().where(
                TenantModelInstance.provider_id.in_(src_provider_ids)))
            old_instance_id_map = {}  # old_instance_id → new_instance_id

            for src_instance in src_instances:
                old_instance_id = src_instance.id
                old_provider_id = src_instance.provider_id

                if old_provider_id not in provider_id_map:
                    logging.warning(f"Provider mapping not found for old_provider_id {old_provider_id}, skipping instance {old_instance_id}")
                    continue

                new_provider_id = provider_id_map[old_provider_id]
                new_instance_id = get_uuid()
                TenantModelInstance.create(
                    id=new_instance_id,
                    instance_name=src_instance.instance_name,
                    provider_id=new_provider_id,
                    api_key=src_instance.api_key,
                    status=src_instance.status,
                    extra=src_instance.extra,
                )
                old_instance_id_map[old_instance_id] = new_instance_id
                result["instances"] += 1
                logging.info(f"Copied instance '{src_instance.instance_name}' ({old_instance_id} → {new_instance_id})")

            # # 第三步: 复制模型 (Step 3: Copy models)
            # if old_instance_id_map:
            #     src_models = list(TenantModel.select().where(
            #         TenantModel.instance_id.in_(list(old_instance_id_map.keys()))))
            #     for src_model in src_models:
            #         old_instance_id = src_model.instance_id
            #         if old_instance_id not in old_instance_id_map:
            #             continue
            #
            #         new_instance_id = old_instance_id_map[old_instance_id]
            #         # 对于 provider_id，需要使用新的 provider_id
            #         old_provider_id_for_model = src_model.provider_id
            #         new_provider_id_for_model = provider_id_map.get(old_provider_id_for_model, old_provider_id_for_model)
            #
            #         new_model_id = get_uuid()
            #         TenantModel.create(
            #             id=new_model_id,
            #             model_name=src_model.model_name,
            #             provider_id=new_provider_id_for_model,
            #             instance_id=new_instance_id,
            #             model_type=src_model.model_type,
            #             status=src_model.status,
            #         )
            #         result["models"] += 1
            #         logging.debug(f"Copied model '{src_model.model_name}' ({src_model.id} → {new_model_id})")

                logging.info(
                    f"Sync complete: copied {result['providers']} providers, "
                    f"{result['instances']} instances, {result['models']} models "
                    f"from user {from_user_id} to user {to_user_id} in tenant {tenant_id}"
        )
        return result
