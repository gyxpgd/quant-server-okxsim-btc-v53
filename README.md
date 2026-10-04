# btc-v53-demo · OKX 官方模拟交易 v53

这是 **OKX 官方 Demo 交易所执行程序**，版本 `1.0.0-demo.2`。程序使用模拟交易 API 查询账户、提交模拟订单并核对成交，不是仅靠公开行情计算收益的本地模型。

默认不启用交易。必须在服务器本地配置专用 Demo API，依次通过检查、执行 `arm-demo`，然后启动服务。本仓库只接受 `mode: "demo"`；运行层另有 Demo 门控，请求携带 `x-simulated-trading: 1`。没有真钱启用或真实试单入口。

**本包用于新建安装和 GitHub 归档。不要覆盖正在运行的实盘程序、凭据或账本，也不要在已绑定账户的运行目录直接 `git pull`。** 已有安装需要迁移评估；不能删除账本重新 arm。Demo 账户端到端验收仍为 `not_run`。

## 从这里开始

| 想做什么 | 阅读文件 |
| --- | --- |
| 第一次部署到 Debian/Linux | [部署步骤](docs/DEPLOY.md) |
| 配置代理、确认是否真正连到 OKX | [代理说明](docs/PROXY.md) |
| 看状态、暂停、平仓、停止 | [日常操作](docs/OPERATIONS.md) |
| 把干净源码推送到 GitHub | [GitHub 归档步骤](docs/GITHUB.md) |
| 了解每个文件 | [文件清单](FILES.md) |
| 核实已测试和未测试内容 | [离线测试报告](TEST-REPORT.md) · [Demo 验收清单](ACCEPTANCE.md) |

推荐 GitHub 仓库名、克隆目录与服务器目录均为 `btc-v53-demo`。真实资金工程单独使用 `btc-v53-live` 仓库、目录及服务，两个仓库分别配置凭据、启用流程与账本。

## 固定配置

配置文件只有项目根目录的 `config.json`。不需要另建 `network.json` 或代理 `.env`。

| 项目 | 默认值 / 约束 |
| --- | --- |
| 环境 | `demo`，不能切换成实盘 |
| 合约 | `BTC-USDT-SWAP` |
| 预算 | 30 USDT 的模拟策略账本；不会按 Demo 账户显示的大额权益扩大预算 |
| 杠杆 | 逐仓 15 倍，用户在 OKX 模拟账户手动设置 |
| 代理 | `http://127.0.0.1:17890`，本机 Mihomo HTTP/mixed 入口 |
| 交易所地址 | 默认 `https://openapi.okx.com`；代码只允许已列出的全球站地址 |
| 轮询 | 10 秒，可接受范围 5–30 秒 |
| 行情预热 | 固定 14 天已确认分钟 K 线，汇总为冻结 v53 信号 |
| 凭据 | 本地 `credentials.env`，当前用户持有，权限 `600` |
| 运行数据 | 本项目 `var/demo/`，不进入 GitHub |
| 用户服务 | `btc-v53-demo.service` |

风险、手续费预算、滑点预算等策略参数也被固定；修改配置不能静默改成另一套策略。手续费检查按合约 `groupId` 选择 `feeGroup.taker`，缺字段、匹配不唯一或费用超过预算时拒绝继续。

六个策略文件的 SHA-256 保存在 `frozen-source-manifest.json`。代码、配置、账户和密钥指纹绑定到首次启用的账本；更换代码或配置后直接复用旧账本会被拒绝。共用的历史账户进程锁目录是 `~/.local/state/btc-v53-live/locks/`，锁键含 `mode + uid`，用于阻止旧安装或另一副本重复运行同一 Demo 账户；它不存放交易账本，也不使 Demo 共用实盘账本。

## 最常用的查看命令

以下命令在已部署的服务器普通用户终端运行：

```bash
cd "$HOME/btc-v53-demo"
python3 status_view.py
python3 launch.py status --local
systemctl --user status btc-v53-demo.service --no-pager
journalctl --user -u btc-v53-demo.service -n 80 --no-pager
```

`status_view.py` 会通过代理访问公开时间接口。`status --local` 不联网，但显示的是上次记录；空仓、止损和成交都要结合记录时间及 OKX Demo 界面确认。

## 本地离线验证

```bash
python3 -m unittest discover -s tests -q
bash -n deploy/install-service.sh
```

项目只使用 Python 标准库，服务器安装要求 Python 3.11 及以上。测试使用合成数据和临时账本，不需要密钥。当前报告中的离线测试通过不代表完成真实 Demo 账户验收，也不能用来推断策略收益。
