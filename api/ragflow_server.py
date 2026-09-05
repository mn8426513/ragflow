#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
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

# =============================================================================
# RAGFlow API 服务器入口模块 (RAGFlow API Server Entry Point)
# =============================================================================
# 这是 RAGFlow 后端的主入口点，负责:
#   1. 初始化日志系统、数据库和服务配置
#   2. 启动 Quart 异步 HTTP 服务器 (Quart 是 Flask 的异步重写版本)
#   3. 管理后台进度更新线程
#   4. 处理优雅关闭信号
#
# RAGFlow 运行时包含两种独立的 Python 进程:
#   - API Server (本文件): Quart 异步 HTTP 服务
#   - Task Executor (rag/svr/task_executor.py): 后台任务执行器，通过 Redis 队列驱动
# =============================================================================

print("Start RAGFlow server...")

import time

start_ts = time.time()

import os

# LiteLLM fetches a model cost map from GitHub during import unless this is set.
# The API server should not block startup on external network access.
# LiteLLM 在导入时会从 GitHub 获取模型成本映射表，设置此环境变量可以阻止该行为，
# 避免 API 服务器启动时因外部网络不可用而阻塞。
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import logging
import signal
import sys
import threading
import uuid
import faulthandler

# Quart 应用实例 (从 api/apps 工厂模块导入)
from api.apps import app
# 运行时配置管理 (Runtime Configuration Management)
from api.db.runtime_config import RuntimeConfig
# 文档服务 - 用于后台进度更新 (Document service for background progress updates)
from api.db.services.document_service import DocumentService
# 获取项目根目录路径 (Get project base directory path)
from common.file_utils import get_project_base_directory
# 全局设置管理 (Global settings management)
from common import settings
# 数据库表初始化 (Database table initialization)
from api.db.db_models import init_database_tables as init_web_db
# 初始数据填充和超级用户创建 (Initial data seeding and superuser creation)
from api.db.init_data import init_web_data, init_superuser
# 获取 RAGFlow 版本号 (Get RAGFlow version string)
from common.versions import get_ragflow_version
# 显示系统配置信息 (Display system configuration information)
from common.config_utils import show_configs
# MCP 会话管理 - 关闭所有 MCP 工具调用会话 (Shutdown all MCP tool call sessions)
from common.mcp_tool_call_conn import shutdown_all_mcp_sessions
# 根日志初始化 (Root logger initialization)
from common.log_utils import init_root_logger
# 全局插件管理器 - 加载外部 LLM 工具插件 (Global plugin manager for external LLM tool plugins)
from agent.plugin import GlobalPluginManager
# Redis 分布式锁 - 用于协调多实例间的任务执行 (Redis-based distributed lock for coordinating tasks across instances)
from rag.utils.redis_conn import RedisDistributedLock

# 停止事件 - 用于协调优雅关闭 (Stop event for graceful shutdown coordination)
stop_event = threading.Event()
chat_channel_thread = None
shutdown_requested = False

RAGFLOW_DEBUGPY_LISTEN = int(os.environ.get("RAGFLOW_DEBUGPY_LISTEN", "0"))


def update_progress():
    """后台进度更新线程函数 (Background progress update thread function)

    定期获取 Redis 分布式锁，然后更新所有文档的处理进度。
    使用分布式锁确保在多实例部署时只有一个实例执行进度更新。
    每 6 秒轮询一次。
    """
    lock_value = str(uuid.uuid4())
    redis_lock = RedisDistributedLock("update_progress", lock_value=lock_value, timeout=60)
    logging.info(f"update_progress lock_value: {lock_value}")
    while not stop_event.is_set():
        acquired = False
        try:
            acquired = redis_lock.acquire()
            if acquired:
                DocumentService.update_progress()
        except Exception:
            logging.exception("update_progress exception")
        finally:
            if acquired:
                try:
                    redis_lock.release()
                except Exception:
                    logging.exception("update_progress exception")
            stop_event.wait(6)


def stop_background_services():
    stop_event.set()
    if chat_channel_thread and chat_channel_thread.is_alive() and chat_channel_thread is not threading.current_thread():
        chat_channel_thread.join(timeout=5)


def signal_handler(sig, frame):
    global shutdown_requested
    if shutdown_requested:
        os.kill(os.getpid(), signal.SIGKILL)
        return
    shutdown_requested = True
    sys.exit(0)


def run_server():
    """信号处理函数 - 处理 SIGINT/SIGTERM 实现优雅关闭 (Graceful shutdown handler)

    1. 关闭所有 MCP 工具调用会话
    2. 设置停止事件以通知后台线程
    3. 退出进程
    """
    logging.info("Received interrupt signal, shutting down...")
    shutdown_all_mcp_sessions()
    stop_background_services()
    sys.exit(0)

if __name__ == '__main__':
    # 启用故障处理器 - 在发生段错误等严重故障时生成 Python 堆栈跟踪
    faulthandler.enable()
    # 初始化根日志记录器
    init_root_logger("ragflow_server")
    logging.info(r"""
        ____   ___    ______ ______ __
       / __ \ /   |  / ____// ____// /____  _      __
      / /_/ // /| | / / __ / /_   / // __ \| | /| / /
     / _, _// ___ |/ /_/ // __/  / // /_/ /| |/ |/ /
    /_/ |_|/_/  |_|\____//_/    /_/ \____/ |__/|__/

    """)
    logging.info(f"RAGFlow version: {get_ragflow_version()}")
    logging.info(f"project base: {get_project_base_directory()}")
    show_configs()
    # 初始化全局设置 - 从 service_conf.yaml 和环境变量加载配置
    settings.init_settings()
    settings.print_rag_settings()

    # 调试模式 - 可附加 VS Code debugpy 远程调试器
    if RAGFLOW_DEBUGPY_LISTEN > 0:
        logging.info(f"debugpy listen on {RAGFLOW_DEBUGPY_LISTEN}")
        import debugpy

        debugpy.listen(("0.0.0.0", RAGFLOW_DEBUGPY_LISTEN))

    # 初始化数据库: 创建表结构并填充初始数据 (Initialize database: create tables and seed initial data)
    init_web_db()
    init_web_data()
    # 初始化运行时配置 (Initialize runtime configuration)
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default=False, help="RAGFlow version", action="store_true")
    parser.add_argument("--debug", default=False, help="debug mode", action="store_true")
    parser.add_argument("--init-superuser", default=False, help="init superuser", action="store_true")
    args = parser.parse_args()
    if args.version:
        print(get_ragflow_version())
        sys.exit(0)

    if args.init_superuser:
        init_superuser()
    RuntimeConfig.DEBUG = args.debug
    if RuntimeConfig.DEBUG:
        logging.info("run on debug mode")

    # 初始化环境配置和运行时配置 (Initialize environment and runtime config)
    RuntimeConfig.init_env()
    RuntimeConfig.init_config(JOB_SERVER_HOST=settings.HOST_IP, HTTP_PORT=settings.HOST_PORT)

    # 加载全局插件 - 从 embedded_plugins/ 目录发现并加载外部 LLM 工具插件
    GlobalPluginManager.load_plugins()

    # 注册信号处理器 - 捕获中断信号以实现优雅关闭
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    def delayed_start_update_progress():
        """延迟启动后台进度更新线程 (Delayed start of progress update thread)

        使用 1 秒延迟是为了确保服务器完全初始化后再开始更新进度。
        在 DEBUG 模式下，使用 WERKZEUG_RUN_MAIN 检测避免在 reloader 子进程中重复启动。
        """
        logging.info("Starting update_progress thread (delayed)")
        t = threading.Thread(target=update_progress, daemon=True)
        t.start()

    def start_chat_channels():
        global chat_channel_thread
        try:
            from api.channels.bootstrap import start_channel_server

            logging.info("Starting chat channel server thread")
            chat_channel_thread = threading.Thread(
                target=start_channel_server,
                args=(stop_event,),
                daemon=True,
                name="chat-channels",
            )
            chat_channel_thread.start()
        except Exception:
            logging.exception("Failed to start chat channel server")

    if RuntimeConfig.DEBUG:
        if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            threading.Timer(1.0, delayed_start_update_progress).start()
            start_chat_channels()
    else:
        threading.Timer(1.0, delayed_start_update_progress).start()
        start_chat_channels()

    # start http server
    logging.info(f"RAGFlow server is ready after {time.time() - start_ts}s initialization.")
    app.run(host=settings.HOST_IP, port=settings.HOST_PORT, use_reloader=RuntimeConfig.DEBUG, debug=False)


def main():
    force_kill = False
    # 启动 HTTP 服务器 (Start HTTP server)
    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        run_server()
    except Exception as e:
        force_kill = True
        logging.exception(f"Unhandled exception: {e}")
    finally:
        if shutdown_requested:
            logging.info("Received interrupt signal, shutting down...")
        try:
            shutdown_all_mcp_sessions()
        finally:
            try:
                stop_background_services()
            finally:
                if force_kill:
                    os.kill(os.getpid(), signal.SIGKILL)


if __name__ == "__main__":
    main()
