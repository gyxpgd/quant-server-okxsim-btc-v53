"""Service orchestration. The delivered candidate is locked to OKX demo."""
from contextlib import ExitStack
import hashlib
from pathlib import Path
import signal
import time

from .config import Attention, AuditPending, code_identity, data_dir, safe_error
from .decisions import exit_order, observe_hour, plan_entry, plan_manage
from .execution import Broker, initial_state
from .market import Market, HOUR, MINUTE, account_snapshot, specification, ticker
from .okx import OKXError
from .store import Store, process_lock


def assert_demo(cfg):
    if cfg['mode'] != 'demo':
        raise Attention('本仓库只允许 OKX 官方 Demo；真实资金启动被锁定，修改mode不能解锁。')


def identity(cfg, creds, uid, spec):
    return dict(code_identity(cfg),uid=uid,mode=cfg['mode'],instrument=cfg['instrument'],
                key_fingerprint=hashlib.sha256(creds['api_key'].encode()).hexdigest(),spec=spec)


def preflight(api,cfg,require_flat=False):
    api.sync_time()
    spec = specification(api)
    q = ticker(api,cfg)
    snapshot = account_snapshot(api,cfg)
    if require_flat:
        if snapshot['position']:
            raise Attention('初次启用必须空仓；不要让程序接管原有仓位。')
        if snapshot['available'] < cfg['capital_usdt']:
            raise Attention('账户可用USDT不足30。模拟账户余额再多，本程序也只按30U预算计算。')
        if api.read('/api/v5/trade/orders-pending',{'limit':'100'},private=True):
            raise Attention('账户存在未完成普通订单；请使用空仓且无挂单的独立模拟账户。')
        # Read all instruments here, not merely BTC. Other strategies must not
        # share the execution account, even if their orders have not filled yet.
        for kind in ('conditional,oco','trigger','move_order_stop','chase','twap','smart_iceberg','iceberg'):
            if api.read('/api/v5/trade/orders-algo-pending',{'ordType':kind,'limit':'100'},private=True):
                raise Attention('账户存在待触发或算法订单；初次启用须为独立空账户。')
    return spec,q,snapshot


def arm_demo(api,cfg,creds):
    assert_demo(cfg)
    directory = data_dir(cfg)
    with process_lock(directory/'runtime.lock'):
        store = Store(directory)
        try:
            spec,q,snap = preflight(api,cfg,require_flat=True)
            ident = identity(cfg,creds,snap['uid'],spec)
            if store.get_state() is not None:
                store.initialize(ident,{})  # Validate identity; never reset equity/state.
                raise Attention('该目录已启用过，不能重新初始化。请查看状态后启动或resume。')
            now = api.now()
            store.initialize(ident,initial_state(now,cfg))
            store.set_health({'phase':'armed','checked_at':now,'mode':cfg['mode'],
                              'message':'已启用模拟盘权限；尚未启动交易循环','public_ok':True,'private_ok':True})
            return {'armed':True,'mode':'demo','capital_usdt':cfg['capital_usdt'],
                    'leverage':cfg['leverage'],'orders_sent':0}
        finally:
            store.close()


class Runtime:
    def __init__(self,api,store,cfg,spec):
        self.api,self.store,self.cfg,self.spec = api,store,cfg,spec
        self.broker = Broker(api,store,cfg,spec)
        self.market = Market(api,store,cfg)
        self.boot_hour = api.now()//HOUR*HOUR
        self.last_sync = time.monotonic()
        self.last_funding = -1e9
        self.stopping = False
        self.last_audit = -1e9

    def controls(self):
        state = self.store.get_state()
        seen = set(state['control_ids'])
        for entry in self.store.record_entries('control'):
            # Store record_entries returns original record key and payload.
            key = entry.get('key',entry.get('record_key'))
            if key in seen:
                continue
            command = entry['payload']['command']
            if command == 'pause':
                state['paused'] = True
                state['last_decision'] = '已暂停开仓及补仓；继续核对和管理已有持仓'
            elif command == 'flatten':
                state['paused'] = True
                # An entry may already be sent while the local position is
                # still None. Persist the exit request until that order is
                # reconciled; otherwise a delayed fill can escape flatten.
                state['closing'] = True
                state['last_decision'] = '已接收平仓请求；成交及空仓需另行确认'
            elif command == 'resume':
                if state['halted']:
                    state['last_decision'] = '风控停止不能用resume解除；需要审查账本和规则'
                else:
                    state['paused'] = False
                    state['last_decision'] = '已恢复，等待下一根新小时信号'
                    state['consumed_hour'] = max(state['consumed_hour'],self.api.now()//HOUR*HOUR)
            else:
                raise Attention('控制队列出现未知指令。')
            seen.add(key)
        state['control_ids'] = sorted(seen)
        self.store.set_state(state)

    def health(self,phase,message,**extra):
        self.store.set_health(dict(phase=phase,checked_at=self.api.now(),mode=self.cfg['mode'],
              message=message,public_ok=True,private_ok=True,
              protection_query_failed=getattr(self,'protection_query_failed',False),
              last_candle=self.store.max_bar_time(),pending_requests=len(self.store.unresolved()),**extra))

    def _protective_read_or_exit(self,action):
        try:
            action()
        except OKXError as exc:
            state = self.store.get_state()
            economic = any(item['kind'] in ('entry','add','exit','cancel_order')
                           for item in self.store.unresolved())
            if not state['closing'] or economic:
                raise
            # A broken algorithm-query endpoint must not starve an already
            # requested exit. No new exposure is allowed: below, actual
            # position equality and fresh quotes are still mandatory, and
            # Broker only permits a reduce-only exit with this uncertainty.
            state['paused'] = True
            self.store.set_state(state)
            self.protection_query_failed = True
            self.store.event('protection_read_unavailable_during_exit',
                             {'action':action.__name__,'reason':safe_error(exc)},self.api.now())

    def _exit(self,quote,reason):
        state = self.store.get_state()
        if not state['position']:
            return
        plan = exit_order(state['position'],quote,self.spec,self.cfg,reason)
        if plan['action'] != 'close':
            raise Attention('持仓尚未平掉，但当前数量或价格不能组成合法退出单；请检查欧易。')
        plan = dict(plan,quote_ts=quote['ts'])
        # One new exit ID only after all earlier economic orders are terminal.
        n = len(self.store.intents('exit'))
        self.broker.submit_order(plan,'exit:'+state['position']['entry_id']+':'+str(n))

    def tick(self):
        self.protection_query_failed = False
        self.controls()
        if time.monotonic()-self.last_sync > 240:
            self.api.sync_time()
            self.last_sync = time.monotonic()
        self.broker.recover_regular()
        self._protective_read_or_exit(self.broker.recover_controls)
        self._protective_read_or_exit(self.broker.native_exits)
        snapshot = account_snapshot(self.api,self.cfg,check_settings=False)
        self.broker.reconcile_position(snapshot)
        self._protective_read_or_exit(self.broker.cleanup_stops)
        state = self.store.get_state()
        # Unknown entry/add/exit is not retryable. Protective amendments may be
        # pending while an explicitly reduce-only emergency exit is necessary.
        pending = self.store.unresolved()
        if any(x['kind'] in ('entry','add','exit','cancel_order') for x in pending):
            self.health('reconciling','仍在核对原订单结果，未发送新的开仓或补仓')
            return
        if state['closing'] and not state['position']:
            # Reconcile_position above confirmed exchange flat, and there is
            # no economic order left that can fill afterwards. Keep pause.
            state['closing'] = False
            self.store.set_state(state)
        quote = ticker(self.api,self.cfg)
        # A requested exit or crossed stop must not depend on successful
        # funding-history reads. Its final fees/bills can reconcile afterwards.
        self.broker.equity(quote)
        state = self.store.get_state()
        p = state['position']
        crossed = bool(p and p['direction']*((quote['bid'] if p['direction'] == 1 else quote['ask'])-p['stop']) <= 0)
        if p and (state['closing'] or state['halted'] or crossed):
            self._exit(quote,'risk_or_requested_exit' if not crossed else 'stop_crossed')
            self.health('closing','已执行退出处理；必须以交易所返回空仓为准')
            return
        if p:
            try:
                protected = self.broker.ensure_protection(p['stop'],p['direction'])
            except Attention:
                state = self.store.get_state()
                state['paused'] = True
                state['closing'] = True
                self.store.set_state(state)
                raise
            if not protected:
                self.health('protection_pending','止损正在核对或已触发；停止新增风险')
                return
        if time.monotonic()-self.last_funding > 60:
            self.broker.update_funding()
            self.last_funding = time.monotonic()
        equity = self.broker.equity(quote)
        state = self.store.get_state()
        p = state['position']
        crossed = bool(p and p['direction']*((quote['bid'] if p['direction'] == 1 else quote['ask'])-p['stop']) <= 0)
        if p and (state['closing'] or state['halted'] or crossed):
            self._exit(quote,'risk_or_requested_exit' if not crossed else 'stop_crossed')
            self.health('closing','已执行退出处理；必须以交易所返回空仓为准')
            return
        if self.store.unresolved():
            self.health('reconciling','保护或撤单尚未确认；停止新增风险')
            return
        if time.monotonic()-self.last_audit > 60:
            self.broker.audit_pending()
            self.broker.audit_fills()
            self.last_audit = time.monotonic()
        frame = self.market.update()
        if frame is None:
            self.health('warming','正在补齐已确认历史数据；不补下历史开仓单')
            return
        # Re-fetch executable quotes after potentially slow historical requests.
        quote = ticker(self.api,self.cfg)
        now = self.api.now()
        state = self.store.get_state()
        if state['position'] and frame['ts'] > state['last_hour']:
            state['position'] = observe_hour(state['position'],frame,self.cfg,self.spec)
        state['last_hour'] = max(state['last_hour'],frame['ts'])
        due = frame['ts']+MINUTE
        fresh = (frame['ts'] > self.boot_hour and frame['ts'] > state['consumed_hour']
                 and due <= now <= due+self.cfg['signal_ttl_seconds']*1000)
        # Consume once before planning/dispatch. Crash here skips an opportunity
        # rather than repeating an economic action after restart.
        if now >= due:
            state['consumed_hour'] = max(state['consumed_hour'],frame['ts'])
        self.store.set_state(state)
        equity = self.broker.equity(quote)
        state = self.store.get_state()
        if state['halted']:
            if state['position']:
                self._exit(quote,'drawdown_stop')
            self.health('halted',state['halted'])
            return
        p = state['position']
        available = max(0.,min(snapshot['available'],state['cash']-(p['margin'] if p else 0)))
        plan = {'action':'hold','reason':'等待新的完整小时信号'}
        if p and now >= due:
            if not p.get('margin_confirmed'):
                raise Attention('尚未确认交易所实际保证金。')
            plan = plan_manage(p,frame,equity,available,quote,self.spec,self.cfg)
            if plan['action'] == 'close':
                self._exit(quote,plan['reason'])
            elif plan['action'] == 'manage':
                confirmed = self.broker.ensure_protection(plan['stop'],p['direction'])
                if plan.get('add') and confirmed and fresh and not state['paused']:
                    # Stop confirmation may itself take time. Replan with a
                    # fresh quote and verify the signal TTL once more.
                    snap = account_snapshot(self.api,self.cfg,check_settings=False)
                    self.broker.reconcile_position(snap)
                    self.broker.audit_pending()
                    self.broker.audit_fills()
                    q = ticker(self.api,self.cfg)
                    latest = self.store.get_state()
                    value = self.broker.equity(q)
                    avail = max(0.,min(snap['available'],latest['cash']-latest['position']['margin']))
                    again = plan_manage(latest['position'],frame,value,avail,q,self.spec,self.cfg)
                    if again['action'] == 'close':
                        self._exit(q,again.get('reason','risk_changed_during_confirmation'))
                    elif (not self.stopping and again['action'] == 'manage' and again.get('add')
                            and self.api.now() <= due+self.cfg['signal_ttl_seconds']*1000):
                        addition = dict(again['add'],quote_ts=q['ts'],
                                        valid_until=due+self.cfg['signal_ttl_seconds']*1000)
                        self.broker.submit_order(addition,'add:'+str(frame['ts']),frame['ts'])
        elif (not self.stopping and not p and fresh and not state['paused']
              and frame['ts'] >= state['cooldown_until'] and now >= state['cooldown_until']):
            # Historical downloads/audits can be slow, and external account
            # changes must never be adopted by blindly adding a new position.
            snap = account_snapshot(self.api,self.cfg,check_settings=False)
            self.broker.reconcile_position(snap)
            self.broker.audit_pending()
            self.broker.audit_fills()
            quote = ticker(self.api,self.cfg)
            latest = self.store.get_state()
            equity = self.broker.equity(quote)
            available = max(0.,min(snap['available'],latest['cash']))
            plan = plan_entry(frame,equity,available,quote,self.spec,self.cfg)
            if plan['action'] == 'entry':
                if not self.stopping and self.api.now() <= due+self.cfg['signal_ttl_seconds']*1000:
                    entry = dict(plan,quote_ts=quote['ts'],
                                 valid_until=due+self.cfg['signal_ttl_seconds']*1000,
                                 signal_close=frame['entry']['close'],atr=frame['entry']['atr'])
                    self.broker.submit_order(entry,'entry:'+str(frame['ts']),frame['ts'])
                    latest = self.store.get_state()
                    if latest['position']:
                        self.broker.ensure_protection(latest['position']['stop'],latest['position']['direction'])
                else:
                    plan = {'action':'hold','reason':'准备下单期间信号过期或进程收到停止请求'}
        state = self.store.get_state()
        state['last_decision'] = plan.get('reason',plan['action'])
        self.store.set_state(state)
        self.health('paused' if state['paused'] else 'running',state['last_decision'])

    def run(self):
        def stop(signum,frame):
            self.stopping = True
        old = {}
        for s in (signal.SIGTERM,signal.SIGINT):
            old[s] = signal.signal(s,stop)
        try:
            while not self.stopping:
                try:
                    self.tick()
                except Exception as exc:
                    # No raw exception/URL/header/API message in logs.
                    message = safe_error(exc)
                    if isinstance(exc,Attention) and not isinstance(exc,AuditPending):
                        # Structural/account/unknown-order problems require a
                        # deliberate resume after review. A transient public
                        # network error may reconnect, but does not clear pause.
                        state = self.store.get_state()
                        state['paused'] = True
                        state['last_decision'] = message
                        self.store.set_state(state)
                    self.store.set_health({'phase':'attention','checked_at':self.api.now(),
                       'mode':self.cfg['mode'],'message':message,'public_ok':False,'private_ok':False,
                       'last_candle':self.store.max_bar_time(),'pending_requests':len(self.store.unresolved())})
                    print(message,flush=True)
                deadline = time.monotonic()+self.cfg['poll_seconds']
                while not self.stopping and time.monotonic() < deadline:
                    time.sleep(min(.25,max(0,deadline-time.monotonic())))
        finally:
            self.store.set_health({'phase':'stopped','checked_at':self.api.now(),'mode':self.cfg['mode'],
               'message':'进程已停止；这不代表平仓。已经确认的交易所止损仍由交易所执行。'})
            for s,handler in old.items():
                signal.signal(s,handler)


def run(api,cfg,creds):
    assert_demo(cfg)
    directory = data_dir(cfg)
    with ExitStack() as stack:
        stack.enter_context(process_lock(directory/'runtime.lock'))
        store = Store(directory)
        stack.callback(store.close)
        if not store.get_state() or not store.get_state().get('armed'):
            raise Attention('尚未arm-demo；服务不能自动初始化或自行启用交易。')
        spec,q,snapshot = preflight(api,cfg)
        store.initialize(identity(cfg,creds,snapshot['uid'],spec),{})
        # Keep the historical shared lock namespace so older installations also
        # cannot run the same demo account from a second directory. The lock
        # identity includes mode; live and demo accounts remain distinct.
        lock_id = hashlib.sha256((cfg['mode']+':'+snapshot['uid']).encode()).hexdigest()
        stack.enter_context(process_lock(Path.home()/'.local/state/btc-v53-live/locks'/(lock_id+'.lock')))
        Runtime(api,store,cfg,spec).run()
