# 首次部署到服务器

本说明用于 **全新的 `~/btc-v53-demo` 安装**。所有命令由你在服务器普通用户终端执行；除安装系统软件和开启 linger 外，不使用 sudo。源码归档本身不会连接账户、创建凭据、arm 或启动服务。

已有 `~/btc-v53-demo`、旧 Demo 账本或正在运行的实盘时，先保留现状。不要把新文件覆盖进去，不要将旧 `var/` 或模型数据复制到新包，也不要在运行目录直接 `git pull`。账本绑定代码、配置、账户与密钥指纹，本包不是原地升级脚本。

## 1. 放置完整项目

服务器需要 Linux 用户级 systemd、Python 3.11 及以上、Git。先查看版本：

```bash
/usr/bin/python3 --version
git --version
systemctl --user show-environment
```

若缺少软件，Debian 可由有权限的管理员安装 `python3`、`git` 和 `unzip`。服务器本身的 Python 版本必须满足要求。

已将仓库推送到 GitHub 后，把下面的 `YOUR_GITHUB_USER` 替换为你的 GitHub 用户名，再执行。私有仓库使用你自己的 GitHub 登录或 SSH 授权，凭据不要写入 URL：

```bash
cd "$HOME"
git clone https://github.com/YOUR_GITHUB_USER/btc-v53-demo.git btc-v53-demo
cd "$HOME/btc-v53-demo"
```

也可以上传完整压缩包，再解压到主目录；压缩包内的顶层文件夹应为 `btc-v53-demo/`。只在目标目录尚不存在时解压，不要使用覆盖选项。最终应能看到：

```text
~/btc-v53-demo/launch.py
~/btc-v53-demo/config.json
~/btc-v53-demo/livecore/
~/btc-v53-demo/deploy/btc-v53-demo.service
```

## 2. 配置本机代理

先阅读 [代理说明](PROXY.md)。本版固定读取 `config.json` 中的：

```json
"proxy": "http://127.0.0.1:17890"
```

Mihomo 应在同一服务器提供这个 HTTP 或 mixed 端口。不要在项目中填写机场订阅、节点密码或代理认证信息。机场节点切换由 Mihomo 管理，量化配置仍使用本机入口。此归档没有新增代理端口范围。

Demo 与实盘可以使用现有同一 Mihomo 服务。**不要为了测试 Demo 断网而停止共用代理、改节点或断开服务器网络，避免影响正在运行的实盘。** 故障测试应留给独立的测试主机和代理。

## 3. 在 OKX 模拟交易中准备账户

进入 OKX 的模拟交易环境，创建这套程序专用的 **Demo API**，不要使用真实交易 API。代码要求读取和交易权限，不接受提币权限。

按程序检查要求，在该模拟账户手动确认：

- 合约模式（代码检查 `acctLv=2`）、买卖/净持仓模式（`net_mode`）。
- `BTC-USDT-SWAP` 为逐仓 15 倍；可用 USDT 至少 30。
- 首次启用前全账户空仓，没有普通挂单或算法挂单；不要与其他机器人共用这个模拟账户。

程序不会自动改账户模式、杠杆或转账。API 如设 IP 限制，需匹配实际代理出口；相关配置只在你自己的交易所和代理管理界面完成。

## 4. 本地填写 Demo API

```bash
cd "$HOME/btc-v53-demo"
python3 launch.py setup-credentials
```

按提示依次输入 API Key、Secret Key 和 Passphrase。输入不回显，程序新建权限为 `600` 的 `credentials.env`，不会联网，也不会下单。已有同名文件时程序拒绝覆盖；不要随手换密钥去复用已启用的账本。

`credentials.env.example` 只是格式示例，不能当作实际凭据使用。不要将真实内容发到聊天、Issue、日志或 GitHub。

## 5. 先检查，再启用 Demo

```bash
python3 launch.py check
python3 launch.py account-check
```

`check` 仅检查公开接口、时间、报价和合约规格；不读取密钥。`account-check` 会读取模拟账户及手续费规则，但不会发交易指令。两条都应显示 `"passed": true` 和 `"orders_sent": 0`。失败时停在这里，按错误和 [日常操作](OPERATIONS.md) 排查，不要删除门控或改策略参数绕过检查。

确认使用专用 Demo 账户、检查全部通过后，由你明确启用：

```bash
python3 launch.py arm-demo
```

成功时显示 `"armed": true`、`"mode": "demo"`、`"orders_sent": 0`。这一步会在 `var/demo/` 创建绑定该账户的本地账本，仍未启动交易循环。它只能执行一次，不能用来清零亏损或重新初始化旧账本。

## 6. 安装并启动独立用户服务

```bash
bash deploy/install-service.sh
loginctl show-user "$(whoami)" -p Linger
```

安装脚本只接受 `~/btc-v53-demo`，安装 `btc-v53-demo.service` 并设置自动启动，本次不启动、不 arm。正在运行或不同内容的同名服务会被保留并拒绝覆盖。服务模板依赖同一用户的 `mihomo-proxy.service`，采用 `Wants`，不会因代理服务退出而被 systemd 连带停止。

若 `Linger=no`，由有 sudo 权限的用户开启：

```bash
sudo loginctl enable-linger "$(whoami)"
```

准备完成后启动：

```bash
systemctl --user start btc-v53-demo.service
python3 status_view.py
journalctl --user -u btc-v53-demo.service -n 80 --no-pager
```

不要同时另开 `python3 launch.py run`；服务已经负责运行。交易服务使用 `%h/btc-v53-demo`，不会指向 `~/btc-v53-live`。

## 7. 确认预热与运行状态

首次启动会看到 `warming`（预热）：程序逐页补齐 14 天已确认行情，每轮最多两页，不会补下历史信号订单。它是下载历史数据，不是必须再等待 14 天。具体耗时取决于接口、网络和数据缺口。

数据完整、账户核对通过后状态可变成 `running`。没有持仓并不代表故障，程序还需要新的完整小时信号、时间窗口和全部风控条件。完成 [Demo 验收清单](../ACCEPTANCE.md) 后才能把自己的账户端到端结果记为已验收；这份归档仍标记 `not_run`。
