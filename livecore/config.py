"""Explicit local configuration. No credentials enter strategy state or logs."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULT = {
    'mode': 'demo', 'instrument': 'BTC-USDT-SWAP',
    'origin': 'https://openapi.okx.com', 'proxy': 'http://127.0.0.1:17890',
    'capital_usdt': 30, 'leverage': 15, 'max_loss_usdt': 30,
    'risk': .06, 'max_notional_multiple': 5, 'reserve': .5,
    'fee': .0005, 'slip': .0003, 'halt_dd': .6, 'cooldown_hours': 6,
    'poll_seconds': 10, 'signal_ttl_seconds': 90, 'quote_age_seconds': 5,
    'warmup_days': 14
}


def load_config(path=None):
    cfg = json.loads(Path(path or ROOT/'config.json').read_text())
    if set(cfg) != set(DEFAULT):
        raise ValueError('配置字段不完整或存在未知字段。')
    if cfg['mode'] != 'demo' or cfg['instrument'] != 'BTC-USDT-SWAP':
        raise ValueError('本仓库仅支持 OKX 官方 demo 和 BTC-USDT-SWAP；真实资金须使用独立仓库。')
    for key in ('capital_usdt','leverage','max_loss_usdt','risk','max_notional_multiple',
                'reserve','fee','slip','halt_dd','cooldown_hours','warmup_days'):
        if type(cfg[key]) not in (int,float) or cfg[key] != DEFAULT[key]:
            raise ValueError('本版本固定为已确认的30U v53规则；不允许通过配置静默更改策略。')
    if type(cfg['poll_seconds']) is not int or not 5 <= cfg['poll_seconds'] <= 30:
        raise ValueError('轮询间隔须为5至30秒。')
    if cfg['signal_ttl_seconds'] != 90 or cfg['quote_age_seconds'] != 5:
        raise ValueError('本版本固定信号和报价过期规则。')
    if cfg['origin'] not in ('https://openapi.okx.com','https://www.okx.com'):
        raise ValueError('接口地址不在全球站允许列表中。区域账户需另行适配，不能自动换域名。')
    if cfg['proxy'] != 'http://127.0.0.1:17890':
        raise ValueError('本交付仅允许已配置的本机Mihomo入口。')
    return cfg


def credentials(path=None):
    path = Path(path or ROOT/'credentials.env')
    if not path.is_file() or path.is_symlink():
        raise ValueError('请在服务器本地创建 credentials.env。不要把密钥发到聊天中。')
    if os.name != 'nt' and (path.stat().st_mode & 0o077 or path.stat().st_uid != os.getuid()):
        raise ValueError('credentials.env必须属于当前用户，权限为600。')
    values = {}
    allowed = {'OKX_API_KEY','OKX_SECRET_KEY','OKX_PASSPHRASE'}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, sep, val = line.partition('=')
        if not sep or key not in allowed or key in values or not val:
            raise ValueError('credentials.env格式错误；每行名称=值，不加引号。')
        values[key] = val
    if set(values) != allowed or any(v.startswith('FILL_') for v in values.values()):
        raise ValueError('密钥配置未完成。')
    return {'api_key':values['OKX_API_KEY'], 'secret_key':values['OKX_SECRET_KEY'],
            'passphrase':values['OKX_PASSPHRASE']}


def data_dir(cfg):
    return ROOT/'var'/cfg['mode']


def code_identity(cfg):
    names = [ROOT/'launch.py'] + sorted((ROOT/'livecore').glob('*.py'))
    manifest = json.loads((ROOT/'frozen-source-manifest.json').read_text())
    for name, expected in manifest.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != expected:
            raise ValueError('冻结的v53信号文件发生变化。')
        names.append(ROOT/name)
    return {'config':cfg,'files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in names}}


def safe_error(exc):
    if isinstance(exc, (ValueError, RuntimeError)) and str(exc):
        # Our public messages never include raw API sMsg, response bodies, or headers.
        from .okx import OKXError
        if isinstance(exc, OKXError):
            return str(exc)
        if getattr(exc, 'safe_message', False):
            return str(exc)
    return type(exc).__name__ + '；请查看脱敏状态并核对服务、代理及账户设置。'


class Attention(RuntimeError):
    safe_message = True


class AuditPending(Attention):
    """Fill evidence is incomplete: abort this tick, then retry without unpausing."""
