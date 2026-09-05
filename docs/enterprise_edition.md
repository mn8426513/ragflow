# RAGFlow 企业版功能

本文档描述本仓库内置的企业版能力。企业版功能默认不改变开源版本行为，只有通过环境变量启用后才会在管理后台与产品界面展示。

## 启用方式

1. 前端构建时设置企业版开关：

```bash
VITE_RAGFLOW_ENTERPRISE=RAGFLOW_ENTERPRISE npm run build
```

2. 启动 admin 服务（端口默认 `9381`）：

```bash
python admin/server/admin_server.py
```

3. 首次启动后系统会自动创建企业版数据表，并初始化 `admin` / `user` 两个内置角色。

## 功能清单

- RBAC 权限：角色 CRUD、按资源（dataset/chat/agent/search/file/team/memory）配置 enable/read/write/share 权限、用户角色分配、用户权限查询。
- 部门管理：部门树 CRUD、部门成员添加/移除、用户部门查询与设置。
- 细粒度知识权限：知识库 ACL，支持按用户、部门、角色授予 read/write/manage；权限层级为 read < write < manage，列表、详情、检索、文档上传、文件关联、更新和删除均按 ACL 判断。
- SSO 登录：支持 OIDC、OAuth2、GitHub 登录渠道；可通过管理后台保存配置，登录页动态展示渠道。
- 操作审计：admin 写操作、用户登录/登出、知识库创建/更新/删除/授权变更均写入审计日志，可在管理后台查询。
- 数据水印：可配置水印开关、文本、透明度与字号；启用后在前端全局叠加基于当前用户身份的水印。
- 安全管控：注册白名单、密码策略（长度/大小写/数字/特殊字符）、登录失败锁定参数、会话超时参数。

## 主要 API

Admin（前缀 `/api/v1/admin`）：

- `GET/POST /departments`，`PUT/DELETE /departments/<id>`，`GET/POST/DELETE /departments/<id>/members`
- `GET/POST/PUT/DELETE /roles`，`POST/DELETE /roles/<name>/permission`，`GET /roles/<name>/permissions`
- `GET /audit/logs`
- `GET/PUT /security/settings`
- `GET/PUT /sso`，`POST /sso/test`
- `GET/POST/PUT/DELETE /whitelist` 相关端点

用户侧（前缀 `/api/v1/enterprise`）：

- `GET /access/targets`
- `GET/PUT /datasets/<dataset_id>/permissions`
- `GET /security/watermark`

## 数据模型

新增数据表：

- `department` / `user_department`
- `role` / `role_permission` / `user_role`
- `knowledgebase_acl`
- `audit_log`
- `whitelist`

安全与 SSO 配置保存在 `system_settings` 表中，key 分别为 `enterprise.security` 与 `enterprise.sso.providers`。
