# OKX 官方 Demo 验收清单

本版本为 `btc-v53-demo` / `1.0.0-demo.2`，**`demo_e2e: not_run`**。下面是部署后由用户在自己的 Demo 账户执行和记录的流程；不是已经完成的验收记录。离线工程测试详见 [TEST-REPORT.md](TEST-REPORT.md)。

只在专用 OKX 模拟账户验收，不使用真实资金 API，不操作 `btc-v53-live.service`。若服务器还运行实盘，Demo 验收不得通过停止共用 Mihomo、改共用节点、重启服务器或中断网络制造故障。需要这些场景时使用独立的测试主机、代理和账户。

## 基础检查

按 [部署说明](docs/DEPLOY.md) 完成全新安装，然后记录日期、版本、步骤及脱敏结果。不要把凭据、账户原始回报或运行账本上传 GitHub。

```bash
cd "$HOME/btc-v53-demo"
python3 launch.py check
python3 launch.py account-check
```

确认两项 `passed: true`、`orders_sent: 0`；Demo 专用 API、账户模式、逐仓 15 倍、至少 30U 可用余额、首次空仓无挂单符合要求。检查失败时，不进入下一步。

## 明确启用与首次启动

```bash
python3 launch.py arm-demo
bash deploy/install-service.sh
systemctl --user start btc-v53-demo.service
python3 status_view.py
```

确认 arm 返回 `mode: demo` 和 `orders_sent: 0`。首次运行应补齐历史行情，在数据就绪后从 `warming` 进入 `running`；记录继续更新，未决请求能解释。不会补下历史信号，正常等待信号不要求人为制造交易。

## 模拟订单与账本

等待策略自然出现合格信号，在 OKX 模拟交易界面确认：

- 合约、方向、逐仓、15 倍以及实际成交数量符合订单和成交记录。
- 成交均价、费用、部分成交与本地记录一致，未成交部分没有变成额外仓位。
- 有仓位时保护订单存在且与当前仓位相符；保护查询异常不增加新风险。
- 平仓后本地与交易所同时确认空仓，逐笔成交核对通过，费用和资金费按实际回报记账。
- 不需要扩大为整个 Demo 账户余额；策略起始预算仍是 30U。

这些内容需要实际 Demo 订单及回报才能确认；本次归档没有执行。

## 控制命令

服务运行时测试 `pause`：确认暂停新开仓/补仓，已有仓位仍被管理。原因排除后再测试 `resume`；风控停止不能用它解除。

测试 `flatten` 时保持服务运行，命令返回只代表请求排队。等最近对账为空仓、无未决经济订单，并在 Demo 界面核对持仓、普通及算法挂单后，才能认定退出完成。

`systemctl --user stop btc-v53-demo.service` 只停进程，不能当作平仓确认。停止后状态应显示已停止或旧记录。再次启动不得重新初始化预算，也不应重复提交原订单。

## 运维验收

退出 SSH 后，再登录确认 `btc-v53-demo.service` 和状态仍正常；检查 `loginctl show-user "$(whoami)" -p Linger`。这不要求中断任何网络或代理。

服务重启、未知订单恢复、交易所止损触发、逐笔账单延迟及服务器重启等高干扰场景，仍需单独的 Demo 测试环境。当前运行实盘的共享服务器不用于破坏性故障演练。

最终验收记录应逐项列出实际观察到的结果及尚未覆盖的场景；不能仅把测试数量或 `systemctl active` 记为端到端验收通过。
