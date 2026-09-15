"""Accounts CRUD + import/export + login/logout + checkpoint + bulk + oauth (§5, §16)."""
from __future__ import annotations

import csv
import io
import json
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from thbuzzer.api.deps import get_session
from thbuzzer.models.all import Account, AccountStatusHistory, ThreadsToken, WarmupPlan
from thbuzzer.security.crypto import encrypt
from thbuzzer.services.logic import WARMUP_DEFAULT

router = APIRouter(prefix="/accounts", tags=["accounts"])
VALID_STATUS = ["new", "login_pending", "two_factor_required", "wrong_password", "warming_up", "active",
                "checkpoint", "restricted", "suspended", "disabled", "retired", "deleted"]


class AccountIn(BaseModel):
    username: str
    password: str = ""
    email: str = ""
    email_password: str = ""
    totp_secret: str = ""
    group_id: int | None = None
    timezone: str = "Asia/Jakarta"
    proxy_id: int | None = None
    account_tier: str = Field(default="buzzer_satellite", pattern="^(brand_official|buzzer_satellite)$")
    account_role: str = Field(default="actor", pattern="^(scout|actor)$")
    default_engine: str = "browser"


@router.get("")
async def list_accounts(status: str = "", group_id: int = 0, limit: int = Query(default=50, ge=1, le=500),
                        offset: int = Query(default=0, ge=0, le=1000000), s=Depends(get_session)):
    q = select(Account).where(Account.deleted == 0)
    if status:
        q = q.where(Account.status == status)
    if group_id:
        q = q.where(Account.group_id == group_id)
    q = q.limit(min(limit, 500)).offset(offset)
    rows = (await s.execute(q)).scalars().all()
    return {"items": [{"id": a.id, "username": a.username, "status": a.status, "health_score": a.health_score,
                       "account_tier": a.account_tier, "account_role": a.account_role} for a in rows]}


@router.post("", status_code=201)
async def create_account(b: AccountIn, s=Depends(get_session)):
    exists = (await s.execute(select(Account).where(Account.username.ilike(b.username)))).scalars().first()
    if exists:
        raise HTTPException(409, "username sudah ada")
    a = Account(username=b.username, status="new", group_id=b.group_id, timezone=b.timezone,
                proxy_id=b.proxy_id, account_tier=b.account_tier, account_role=b.account_role,
                default_engine=b.default_engine if b.account_tier == "buzzer_satellite" else "official_api")
    s.add(a)
    await s.flush()
    a.password_enc = encrypt(b.password, "accounts.password_enc", str(a.id)) if b.password else ""
    a.email = b.email
    import secrets as _sec
    fp = {"app_version": "1.0", "device_id": _sec.token_hex(8), "uuid": _sec.token_hex(8)}
    a.device_params_json = json.dumps(fp)  # fingerprint stabil sekali (§5.4)
    await s.commit()
    return {"id": a.id, "username": a.username, "status": a.status}


@router.post("/import-csv")
async def import_csv(body: dict, s=Depends(get_session)):
    """Bulk CSV §5.3 header WAJIB. Antre login berurutan 30-120 dtk (dijadwalkan caller)."""
    content: str = body.get("csv", "")
    reader = csv.DictReader(io.StringIO(content))
    required = {"username", "password", "email", "email_password", "proxy", "totp_secret", "timezone",
                "country", "group", "tags", "priority", "account_tier", "account_role", "threads_user_id", "oauth_token"}
    if not required.issubset(set(reader.fieldnames or [])):
        raise HTTPException(422, f"header CSV tidak valid: wajib {sorted(required)}")
    ok, bad = 0, []
    for i, row in enumerate(reader, 1):
        try:
            if not row["username"]:
                raise ValueError("username tidak valid: wajib diisi")
            if (row.get("account_tier") or "buzzer_satellite") not in ("brand_official", "buzzer_satellite"):
                raise ValueError(f"account_tier tidak valid: '{row.get('account_tier')}'")
            if (row.get("account_role") or "actor") not in ("scout", "actor"):
                raise ValueError(f"account_role tidak valid: '{row.get('account_role')}'")
            s.add(Account(username=row["username"], status="new",
                          timezone=row.get("timezone") or "Asia/Jakarta",
                          account_tier=row.get("account_tier") or "buzzer_satellite",
                          account_role=row.get("account_role") or "actor",
                          threads_user_id=row.get("threads_user_id") or ""))
            ok += 1
        except Exception as e:  # noqa: BLE001
            bad.append({"row": i, "error": str(e)})
    await s.commit()
    return {"imported": ok, "invalid": bad, "note": "login baru dibatasi 20/jam global (§5.3)"}


@router.post("/{account_id}/status")
async def set_status(account_id: int, body: dict, s=Depends(get_session)):
    to = body.get("status", "")
    if to not in VALID_STATUS:
        raise HTTPException(422, "status tidak dikenal")
    a = await s.get(Account, account_id)
    if not a:
        raise HTTPException(404, "akun tidak ada")
    old = a.status
    a.status = to
    a.updated_at = int(time.time())
    s.add(AccountStatusHistory(account_id=a.id, old_status=old, new_status=to, reason=body.get("reason", "")))
    await s.commit()
    try:
        from thbuzzer.api.hub import broadcast
        await broadcast("account.status_changed", {"account_id": a.id, "status": to})
    except Exception:
        pass
    return {"ok": True, "status": to}


@router.post("/{account_id}/login")
async def login(account_id: int, s=Depends(get_session)):
    """Antre login berurutan (maks 20 login baru/jam global ditegakkan worker via limiter)."""
    from thbuzzer.tasks.queue import enqueue
    a = await s.get(Account, account_id)
    if not a:
        raise HTTPException(404, "akun tidak ada")
    a.status = "login_pending"
    await s.flush()
    job = await enqueue(s, "login", account_id=a.id, priority="high", payload={},
                        dedup_key=f"login:{a.id}")
    await s.commit()
    return {"job_id": job.id, "status": "login_pending"}


@router.post("/{account_id}/logout")
async def logout(account_id: int, s=Depends(get_session)):
    a = await s.get(Account, account_id)
    if not a:
        raise HTTPException(404, "akun tidak ada")
    a.session_blob_enc = ""
    a.storage_state_enc = ""
    if not a.password_enc:
        a.needs_password = 1
    await s.commit()
    return {"ok": True}


@router.post("/{account_id}/verify-2fa")
async def verify_2fa(account_id: int, body: dict, s=Depends(get_session)):
    """Jalur kode manual: tutup event checkpoint/2FA terbuka -> active (limit 50% 24 jam dicatat)."""
    from thbuzzer.models.all import CheckpointEvent
    a = await s.get(Account, account_id)
    if not a:
        raise HTTPException(404, "akun tidak ada")
    if not body.get("code"):
        raise HTTPException(422, "code wajib")
    q = await s.execute(select(CheckpointEvent).where(
        CheckpointEvent.account_id == a.id, CheckpointEvent.status == "open"))
    n = 0
    for ev in q.scalars().all():
        ev.status = "closed"
        n += 1
    old = a.status
    a.status = "active"
    a.updated_at = int(time.time())
    s.add(AccountStatusHistory(account_id=a.id, old_status=old, new_status="active",
                               reason="2FA manual ok; limit 50% 24 jam"))
    await s.commit()
    return {"ok": True, "closed_events": n, "status": "active"}


@router.get("/checkpoint-queue")
async def checkpoint_queue(s=Depends(get_session)):
    from thbuzzer.models.all import CheckpointEvent
    rows = (await s.execute(select(CheckpointEvent).where(CheckpointEvent.status == "open")
                            .order_by(CheckpointEvent.id.desc()).limit(200))).scalars().all()
    return {"items": [{"id": e.id, "account_id": e.account_id, "kind": e.kind,
                       "status": e.status, "created_at": e.created_at} for e in rows]}


@router.post("/{account_id}/resolve-checkpoint")
async def resolve_checkpoint(account_id: int, s=Depends(get_session)):
    """Checkpoint manual via BrowserView: antre job browser prioritas critical."""
    from thbuzzer.tasks.queue import enqueue
    a = await s.get(Account, account_id)
    if not a:
        raise HTTPException(404, "akun tidak ada")
    job = await enqueue(s, "resolve_checkpoint", account_id=a.id, priority="critical",
                        payload={}, engine_hint="browser", dedup_key=f"rc:{a.id}")
    await s.commit()
    return {"job_id": job.id}


@router.post("/bulk")
async def bulk(body: dict, s=Depends(get_session)):
    """pause/resume/limit/engine/proxy/status/delete/export/tes — destruktif >20 butuh confirm."""
    from thbuzzer.tasks.worker import kill
    from thbuzzer.utils.validators import Invalid as _Inv, fail as _fail, int_list as _il, one_of as _one, pos_int as _pi
    try:
        ids = _il(body.get("ids", []), "ids")
        op = _one(body.get("op", ""), "op",
                  {"pause", "resume", "status", "engine", "proxy", "delete", "disable"})
    except _Inv as e:
        raise _fail(str(e))
    if op in ("delete", "disable") and len(ids) > 20 and not body.get("confirm"):
        raise HTTPException(422, "konfirmasi tidak valid: wajib confirm=true untuk >20 akun")
    out = {"op": op, "affected": 0}
    if op == "status":
        try:
            _one(body.get("status", ""), "status", set(VALID_STATUS))
        except _Inv as e:
            raise _fail(str(e))
    if op == "engine":
        try:
            _one(body.get("engine", ""), "engine", {"official_api", "browser", "private_unofficial"})
        except _Inv as e:
            raise _fail(str(e))
    proxy_id = None
    if op == "proxy":
        try:
            proxy_id = _pi(body.get("proxy_id"), "proxy_id")
        except _Inv as e:
            raise _fail(str(e))
    for aid in ids:
        a = await s.get(Account, aid)
        if not a:
            continue
        if op == "pause":
            kill.account_kill.add(aid)
        elif op == "resume":
            kill.account_kill.discard(aid)
        elif op == "status" and body.get("status") in VALID_STATUS:
            a.status = body["status"]
        elif op == "engine":
            a.default_engine = body.get("engine", a.default_engine)
        elif op == "proxy":
            a.proxy_id = proxy_id
        elif op == "delete":
            a.deleted = 1
        elif op == "disable":
            a.status = "disabled"
        out["affected"] += 1
    await s.commit()
    return out


@router.get("/groups")
async def groups(s=Depends(get_session)):
    from thbuzzer.models.all import AccountGroup
    rows = (await s.execute(select(AccountGroup))).scalars().all()
    return {"items": [{"id": g.id, "name": g.name} for g in rows]}


@router.post("/groups", status_code=201)
async def create_group(body: dict, s=Depends(get_session)):
    from thbuzzer.models.all import AccountGroup
    from thbuzzer.utils.validators import Invalid as _InvG, fail as _failG, non_empty as _ne
    try:
        name = _ne(body.get("name"), "name", max_len=100)
    except _InvG as e:
        raise _failG(str(e))
    q = await s.execute(select(AccountGroup).where(AccountGroup.name == name))
    if q.scalars().first():
        raise HTTPException(409, f"grup tidak valid: '{name}' sudah ada")
    g = AccountGroup(name=name)
    s.add(g)
    await s.commit()
    return {"id": g.id}


@router.get("/warmup-plans")
async def warmup_plans(s=Depends(get_session)):
    rows = (await s.execute(select(WarmupPlan))).scalars().all()
    return {"items": [{"id": w.id, "name": w.name} for w in rows],
            "default": WARMUP_DEFAULT}


@router.post("/warmup-plans", status_code=201)
async def create_warmup(body: dict, s=Depends(get_session)):
    w = WarmupPlan(name=body.get("name", "custom"), spec_json=json.dumps(body.get("spec", {})))
    s.add(w)
    await s.commit()
    return {"id": w.id}


@router.post("/{account_id}/warmup")
async def assign_warmup(account_id: int, body: dict, s=Depends(get_session)):
    from thbuzzer.utils.validators import Invalid as _InvW, fail as _failW, pos_int as _piW
    a = await s.get(Account, account_id)
    if not a:
        raise HTTPException(404, "akun tidak ada")
    if body.get("plan_id") is not None:
        try:
            a.warmup_plan_id = _piW(body.get("plan_id"), "plan_id")
            if not await s.get(WarmupPlan, a.warmup_plan_id):
                raise _failW("plan_id tidak valid: rencana tidak ada")
        except _InvW as e:
            raise _failW(str(e))
    else:
        a.warmup_plan_id = None
    a.status = "warming_up"
    await s.commit()
    return {"ok": True, "status": "warming_up"}


@router.get("/{account_id}/export")
async def export_account(account_id: int, include_secrets: bool = False,
                         confirm: bool = False, s=Depends(get_session)):
    a = await s.get(Account, account_id)
    if not a:
        raise HTTPException(404, "akun tidak ada")
    if include_secrets and not confirm:
        raise HTTPException(422, "export secrets wajib confirm=true")
    d = {"id": a.id, "username": a.username, "status": a.status, "account_tier": a.account_tier,
         "account_role": a.account_role, "timezone": a.timezone}
    if include_secrets:
        d["has_password"] = bool(a.password_enc)
        d["has_oauth"] = bool(a.oauth_token_id)
        d["has_session"] = bool(a.session_blob_enc or a.storage_state_enc)
    return d


@router.post("/{account_id}/profile")
async def update_profile(account_id: int, body: dict, s=Depends(get_session)):
    """Edit profil massal: name/bio(<=150)/link(<=5)/privat. 1 job/akun, maks 50/hari/grup (worker)."""
    from thbuzzer.tasks.queue import enqueue
    a = await s.get(Account, account_id)
    if not a:
        raise HTTPException(404, "akun tidak ada")
    bio = body.get("bio", "")
    if len(bio) > 150:
        raise HTTPException(422, "bio tidak valid: maksimal 150 karakter")
    links = body.get("links", [])
    if len(links) > 5:
        raise HTTPException(422, "links tidak valid: maksimal 5 link")
    from thbuzzer.utils.validators import Invalid as _InvP, fail as _failP, http_url as _hu
    try:
        links = [_hu(u, "links[]") for u in links]
    except _InvP as e:
        raise _failP(str(e))
    job = await enqueue(s, "profile_update", account_id=a.id, priority="low",
                        payload={"name": str(body.get("name", ""))[:100], "bio": bio,
                                 "links": links, "private": bool(body.get("private", False))},
                        dedup_key=f"prof:{a.id}")
    await s.commit()
    return {"job_id": job.id}


@router.get("/oauth/status")
async def oauth_status(s=Depends(get_session)):
    rows = (await s.execute(select(ThreadsToken))).scalars().all()
    return {"items": [{"id": t.id, "account_id": t.account_id, "expires_at": t.expires_at} for t in rows]}
