# 本版本离线测试报告

项目：`btc-v53-demo`。版本：`1.0.0-demo.2`。日期：2026-10-04。

本版本在 macOS / Python 3.9.6 上运行完整离线套件，**270 项通过，失败 0 项**。服务安装脚本仍要求服务器 Python 3.11 及以上；本机结果不能代替目标 Linux/systemd 的实际验收。

## 执行与范围

```bash
python3 -m unittest discover -s tests -q
bash -n deploy/install-service.sh
```

完整套件使用临时数据库、合成行情、假订单回报和内存 HTTP 接口。没有使用真实凭据、读取私有账户、发送交易所订单或操作现有服务器与服务。

| 测试文件 | 数量 |
| --- | ---: |
| `test_config.py` | 16 |
| `test_decisions.py` | 37 |
| `test_execution.py` | 32 |
| `test_fill_audit.py` | 27 |
| `test_lifecycle.py` | 1 |
| `test_market.py` | 35 |
| `test_okx.py` | 50 |
| `test_runtime.py` | 42 |
| `test_status_cli.py` | 11 |
| `test_store.py` | 18 |
| `test_system_integration.py` | 1 |
| **合计** | **270** |

`bash -n` 服务安装脚本语法检查通过。六个冻结策略文件与 `frozen-source-manifest.json` 中的 SHA-256 全部一致。新包保持未启用，没有 `credentials.env` 或运行账本。

## 本次重点回归

- 配置加载器拒绝 `live` 及其他非 Demo 模式；运行层的 Demo 门控保持有效，未启用的服务不能自行初始化交易。
- 部署目录、安装模板和状态查询统一为 `btc-v53-demo` / `btc-v53-demo.service`，不会安装到实盘目录或查询实盘服务。
- 手续费使用 `public/instruments.groupId` 动态匹配 `account/trade-fee.feeGroup.taker`；覆盖组顺序变化、旧字段干扰、费用超预算、重复/缺失组及无效数值，失败时拒绝继续。
- 内存 HTTP 集成夹具同步到现代费用组字段，真实模块衔接的只读预检和首次预热循环通过。

既有回归继续覆盖：固定 v53 决策、签名与 Demo 请求标记、强制代理、报价与信号过期、IOC 成交、未知订单恢复、止损保护、逐笔成交审计、资金费账单、数据库恢复、跨副本进程锁、控制请求及陈旧状态显示。

## 未完成的验收

`VERSION.json` 保持 `demo_e2e: not_run` 及账户端到端验收 `not_run`。本次未进行：

- 使用专用 OKX Demo API 的真实账户检查、模拟下单和完整退出。
- 实际接口中的部分成交、止损触发、未知结果恢复和逐笔账单延迟验证。
- 目标 Linux 用户服务、SSH 退出后运行、重启与隔离环境故障演练。
- 长期运行或真实资金环境验收。

[ACCEPTANCE.md](ACCEPTANCE.md) 给出用户后续可执行的 Demo 验收步骤。本仓库不提供真实资金启用入口；离线通过不代表盈利或止损成交保证。

## GitHub 交付包复核

最终源码 ZIP 解压后，在 macOS / Python **3.12.14** 上再次运行同一离线套件：**270 项全部通过**。此前 Python 3.9.6 的结果也保留如上。此复核没有连接服务器、私有账户或发送订单。GitHub CI 的 Python 3.11/3.13 结果须以用户上传后实际运行结果为准。

另已核对：

- ZIP 完整解压、仓库内文档链接、六个冻结策略哈希。
- 服务安装脚本的 Bash 语法；两套服务的独立路径。
- 归档不含实际凭据、订阅、二进制、运行账本或日志。
- Git 忽略规则和暂存区检查；包括重复凭据占位、单行/嵌套 JSON 凭据字段、已暂存后本地修改的内容，以及符号链接拒绝。

`tools/check_repo.py` 是常见文件误上传检查，不是全面的秘密检测系统。
