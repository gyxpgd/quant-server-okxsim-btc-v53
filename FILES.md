# 文件清单

| 路径 | 作用 |
| --- | --- |
| `README.md` | 项目用途、环境边界、阅读入口 |
| `docs/DEPLOY.md` | 全新服务器安装与本地 Demo 配置流程 |
| `docs/OPERATIONS.md` | 状态、暂停/平仓/停止、排查和备份 |
| `docs/PROXY.md` | 本机固定代理和连通性检查 |
| `docs/GITHUB.md` | 干净源码仓库归档步骤 |
| `ACCEPTANCE.md` | 尚待用户执行的官方 Demo 验收 |
| `TEST-REPORT.md` | 本版本已完成的离线验证范围 |
| `VERSION.json` | 名称、版本和 `demo_e2e: not_run` 状态 |
| `config.json` | Demo 固定策略和本机代理入口，无密钥 |
| `credentials.env.example` | 本地凭据格式示例，含占位值 |
| `launch.py` | 配置凭据、检查、arm、运行和控制命令 |
| `status_view.py` | 熟悉的单命令只读状态入口 |
| `livecore/config.py` | Demo 配置、凭据权限、冻结源和代码身份校验 |
| `livecore/okx.py` | 认证、强制代理、Demo 请求标记和受限交易接口 |
| `livecore/market.py` | 合约/行情/账户校验与现代费用组解析 |
| `livecore/decisions.py` | 将冻结 v53 信号转为可执行决策 |
| `livecore/execution.py` | 订单、成交、费用、仓位与保护处理 |
| `livecore/runtime.py` | Demo 门控、启用、运行循环及重启核对 |
| `livecore/store.py` | SQLite 账本、请求记录和进程锁 |
| `livecore/status.py` | 状态展示和公开接口探测 |
| `strategy.py`、`quality.py`、`capture.py`、`confirmation.py`、`variants.py`、`model_engine.py` | 六个冻结策略文件，保持原文件逐字节一致 |
| `frozen-source-manifest.json` | 六个冻结文件的 SHA-256 |
| `tests/` | 临时账本、合成数据、内存 HTTP 的离线回归测试 |
| `deploy/btc-v53-demo.service` | 独立 Demo 用户级 systemd 服务模板 |
| `deploy/install-service.sh` | 仅安装/启用服务，不启动、不 arm |
| `tools/`、`.github/` | 归档检查工具和仓库自动检查配置 |
| `.gitignore`、`.gitattributes` | 防止运行数据入库并固定文件换行行为 |

运行后产生的以下文件不属于发布源码：

- `credentials.env`：只在自己的服务器保存，权限 `600`。
- `var/demo/`：本程序独立模拟交易账本、缓存和锁，不可复制为实盘账本。
- `__pycache__/`、日志、临时文件：本地生成物。
- `~/.config/systemd/user/btc-v53-demo.service`：安装后的用户服务。
- `~/.local/state/btc-v53-live/locks/`：沿用旧工程名的跨副本账户锁目录，键包含模式和账户身份；与项目账本分离。

## GitHub 归档辅助文件

- `.gitignore`：帮助排除密钥、订阅、账本、日志和下载的二进制。
- `.gitattributes`：保持脚本使用 Linux 换行。
- `tools/check_repo.py`：上传前检查常见私有文件误提交；`--staged` 检查本次准备提交的 Git 内容。
- `.github/workflows/offline-tests.yml`：GitHub Actions 离线测试，不运行交易服务。
- `docs/GITHUB.md`：首次上传和以后修改的步骤。
- `tools/mihomo/` 与 `docs/PROXY.md`：独立代理的配置助手、服务模板及安装说明，不含节点配置或代理程序二进制。
