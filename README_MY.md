# 重点配置项
## docker/.env 文件，修改 mysql 等的密码
- 例如 ： MYSQL_PASSWORD=ragflow@123

## conf/service_conf.yaml 文件
- 使用 docker/docker-compose.yml启动Docker时，容器启动时会自动重写 conf/service_conf.yaml。在 [docker/entrypoint.sh (line 161)](D:/Users/Administrator/PycharmProjects/ragflow/docker/entrypoint.sh:161) 里，启动流程会先删除 service_conf.yaml，


- 然后读取 service_conf.yaml.template，把其中的 ${VAR:-默认值} 按环境变量替换后重新生成配置文件。所以手动直接改 service_conf.yaml，下次容器启动时很可能被覆盖。


- 直接运行 [docker/launch_backend_service.sh (line 146)](D:/Users/Administrator/PycharmProjects/ragflow/docker/launch_backend_service.sh:146) 则不会。这个脚本只是用 --config conf/service_conf.yaml 去读取配置，代码里也没有找到写回该文件的逻辑。


## 日志相关
- ragflow_server 日志目录位于 /opt/ragflow/logs/ragflow_server.log

// 允许所有主机访问（开发环境测试用）
allowedHosts: ['ymbxnp.space-xboard.ggff.net'],