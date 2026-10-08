"""Audit regression probe for the 2026-10-07 audit findings.

Drives the real FastAPI application (real JWT login, no dependency overrides)
against a DISPOSABLE local PostgreSQL database and reports, per remediation
task, whether the audited defect is still present.

Usage (from the backend/ directory, after `alembic upgrade head`):

    AUDIT_PROBE_DATABASE_URL=postgresql+asyncpg://user:pass@127.0.0.1:55432/fin_audit_disposable \
        .venv/bin/python ../tools/audit/regression_probe.py

Exit code: 0 when no in-scope defect is present, 1 otherwise. Rows marked
DECISION describe behaviour that awaits a business-policy decision and never
affect the exit code. Every run creates a fresh organization; data is left in
place, so only point this at a throwaway database.
"""
import asyncio
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

URL = os.environ.get("AUDIT_PROBE_DATABASE_URL", "")
_parts = urlsplit(URL)
_db_name = (_parts.path or "").lstrip("/").lower()
if (
    _parts.scheme != "postgresql+asyncpg"
    or _parts.hostname not in {"localhost", "127.0.0.1"}
    or not any(token in _db_name for token in ("test", "disposable", "audit"))
):
    sys.exit("Refusing to run: AUDIT_PROBE_DATABASE_URL must be a local postgresql+asyncpg URL "
             "whose database name contains 'test', 'disposable' or 'audit'.")

os.environ["DATABASE_URL"] = URL
os.environ["DEBUG"] = "false"
sys.path.insert(0, str(Path.cwd()))

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from src.core.database import AsyncSessionLocal
from src.core.security import hash_password
from src.main import create_application
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.counterparty import Counterparty
from src.models.enums import ProjectStatus, UserRole
from src.models.organization import Organization
from src.models.project import Project
from src.models.user import User
from src.services.coa_seeder import seed_standard_coa

PASSWORD = "Passw0rd!audit"
RESULTS: list[tuple[str, str, str, str]] = []


def report(task: str, title: str, defect_present: bool, detail: str, decision: bool = False) -> None:
    state = "DECISION" if decision else ("DEFECT" if defect_present else "OK")
    RESULTS.append((task, state, title, detail))
    print(f"[{state:8}] {task} {title}: {detail}", flush=True)


async def setup() -> dict:
    org_id = uuid4()
    ids: dict = {"org": org_id}
    async with AsyncSessionLocal() as s:
        s.add(Organization(id=org_id, slug=f"audit-{org_id.hex[:8]}", legal_name="Audit Probe Org"))
        await s.flush()
        for role in (UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR):
            ids[role.value] = uuid4()
            s.add(User(id=ids[role.value], organization_id=org_id,
                       email=f"{role.value.lower()}-{org_id.hex[:8]}@audit.test",
                       full_name=role.value, password_hash=hash_password(PASSWORD), role=role))
        await s.flush()
        await seed_standard_coa(s, org_id)
        cash = await s.scalar(select(ChartOfAccount).where(
            ChartOfAccount.organization_id == org_id, ChartOfAccount.account_code == "1101"))
        for key, vendor, customer in (("vendor_a", True, False), ("vendor_b", True, False), ("customer", False, True)):
            ids[key] = uuid4()
            s.add(Counterparty(id=ids[key], organization_id=org_id, name=f"{key}-{org_id.hex[:8]}",
                               is_vendor=vendor, is_customer=customer, is_active=True))
        await s.flush()
        ids["project"] = uuid4()
        s.add(Project(id=ids["project"], organization_id=org_id, project_code=f"PRJ-{org_id.hex[:8]}",
                      project_name="Audit Project", project_status=ProjectStatus.ACTIVE,
                      original_contract_value=Decimal("100000000.00"), start_date=date(2026, 1, 1),
                      customer_id=ids["customer"]))
        ids["pa"] = uuid4()
        s.add(PaymentAccount(id=ids["pa"], organization_id=org_id, coa_account_id=cash.id, name="Bank",
                             bank_name="BCA", account_number="123", is_active=True))
        await s.commit()
    return ids


async def scalar(sql: str, **params):
    async with AsyncSessionLocal() as s:
        return await s.scalar(text(sql), params)


async def gl_net(org_id, code: str) -> Decimal:
    return Decimal(await scalar(
        """SELECT coalesce(sum(jl.debit_amount),0) - coalesce(sum(jl.credit_amount),0)
           FROM journal_lines jl JOIN journal_entries je ON je.id = jl.journal_entry_id
           JOIN chart_of_accounts c ON c.id = jl.account_id
           WHERE je.organization_id = :o AND c.account_code = :c""", o=org_id, c=code))


async def main() -> int:
    ids = await setup()
    app = create_application()
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://probe") as c:
        async def login(role: str) -> dict:
            r = await c.post("/api/v1/auth/login", json={
                "email": f"{role.lower()}-{ids['org'].hex[:8]}@audit.test", "password": PASSWORD})
            assert r.status_code == 200, r.text
            return {"Authorization": f"Bearer {r.json()['access_token']}", "X-Organization-ID": str(ids["org"])}

        mgr, op = await login("MANAGER"), await login("OPERATOR")
        today = date.today().isoformat()

        async def create(headers, **kw):
            body = {"transaction_date": today, "description": "audit probe", **kw}
            body["amount"] = str(body["amount"])
            return await c.post("/api/v1/transactions", json=body, headers=headers)

        async def approve(headers, trx_id):
            return await c.post(f"/api/v1/transactions/{trx_id}/approve", headers=headers)

        async def reverse(trx_id, reason="audit probe reversal"):
            return await c.post(f"/api/v1/transactions/{trx_id}/reverse", headers=mgr, json={"reason": reason})

        # T07: created_by recorded on API-created transactions
        r = await create(op, transaction_type="DIRECT_PURCHASE", amount=Decimal("1000.00"),
                         payment_account_id=str(ids["pa"]), project_id=str(ids["project"]), cost_category="MAT")
        trx = r.json()
        report("T07", "created_by recorded", trx.get("created_by") != str(ids["OPERATOR"]),
               f"create={r.status_code} created_by={trx.get('created_by')}")
        a = await approve(op, trx["id"])
        report("D1", "creator may approve own transaction", a.status_code == 200,
               f"self-approve by OPERATOR={a.status_code}", decision=True)
        posted_id = trx["id"]

        # T06: re-approving a POSTED transaction must be a clean 422, never 500
        r = await approve(mgr, posted_id)
        report("T06", "re-approve POSTED returns 422", r.status_code != 422, f"status={r.status_code}")

        # T03: review flags must not move a POSTED transaction out of POSTED
        r = await c.post(f"/api/v1/transactions/{posted_id}/review-flags", headers=op,
                         json={"flag": "DUPLICATE_SUSPECTED", "message": "audit probe flag"})
        status_after = (await c.get(f"/api/v1/transactions/{posted_id}", headers=op)).json()["workflow_status"]
        report("T03", "POSTED transaction immutable under review flags", status_after != "POSTED",
               f"flag={r.status_code} status_after={status_after}")

        # T04: a REVERSAL transaction must not itself be reversible
        r = await create(mgr, transaction_type="BANK_CHARGE", amount=Decimal("15.00"), payment_account_id=str(ids["pa"]))
        await approve(mgr, r.json()["id"])
        rv1 = await reverse(r.json()["id"])
        rv2 = await reverse(rv1.json()["id"]) if rv1.status_code == 201 else None
        report("T04", "reversal of a REVERSAL rejected", bool(rv2 is not None and rv2.status_code == 201),
               f"rev1={rv1.status_code} rev2={rv2.status_code if rv2 is not None else 'n/a'}")

        # T05: concurrent reversals of the same transaction produce exactly one reversal
        r = await create(mgr, transaction_type="BANK_CHARGE", amount=Decimal("17.00"), payment_account_id=str(ids["pa"]))
        target = r.json()["id"]
        await approve(mgr, target)
        responses = await asyncio.gather(*[reverse(target, f"concurrent reversal {i}") for i in range(4)])
        n = await scalar("SELECT count(*) FROM transactions WHERE reversal_of_id = :t", t=target)
        unique_idx = await scalar(
            """SELECT count(*) FROM pg_indexes WHERE tablename = 'transactions'
               AND indexdef ILIKE '%UNIQUE%' AND indexdef ILIKE '%reversal_of_id%'""")
        report("T05", "single reversal enforced by database", n != 1 or not unique_idx,
               f"statuses={[x.status_code for x in responses]} reversals={n} unique_index={bool(unique_idx)}")

        # T10: two vendors may use the same invoice number
        outcomes = []
        for vendor in ("vendor_a", "vendor_b"):
            r = await create(mgr, transaction_type="VENDOR_BILL", amount=Decimal("500.00"),
                             counterparty_id=str(ids[vendor]), reference_no="INV-001",
                             project_id=str(ids["project"]), cost_category="MAT")
            outcomes.append((await approve(mgr, r.json()["id"])).status_code)
        report("T10", "same invoice number across vendors", outcomes != [200, 200], f"post statuses={outcomes}")
        r = await create(mgr, transaction_type="VENDOR_BILL", amount=Decimal("501.00"),
                         counterparty_id=str(ids["vendor_a"]), reference_no="INV-001",
                         project_id=str(ids["project"]), cost_category="MAT")
        report("T10", "same vendor + same invoice number flagged", r.json().get("workflow_status") != "REVIEW_REQUIRED",
               f"create={r.status_code} status={r.json().get('workflow_status')}")

        # T09: SUBCONTRACTOR_BILL must create an AP sub-ledger bill
        before = await gl_net(ids["org"], "2101")
        r = await create(mgr, transaction_type="SUBCONTRACTOR_BILL", amount=Decimal("777.00"),
                         counterparty_id=str(ids["vendor_a"]), project_id=str(ids["project"]), cost_category="SUB")
        p = await approve(mgr, r.json()["id"])
        bills = await scalar("SELECT count(*) FROM vendor_bills WHERE transaction_id = :t", t=r.json()["id"])
        delta = await gl_net(ids["org"], "2101") - before
        report("T09", "SUBCONTRACTOR_BILL creates AP bill", p.status_code == 200 and bills != 1,
               f"post={p.status_code} vendor_bills={bills} AP GL delta={delta}")

        # T11: generic JOURNAL_ADJUSTMENT must not touch AR/AP control accounts
        r = await create(op, transaction_type="JOURNAL_ADJUSTMENT", amount=Decimal("1998.00"),
                         allocations=[{"amount": "999.00", "notes": "DR:1201"}, {"amount": "999.00", "notes": "CR:4101"}])
        report("T11", "adjustment into AR control account rejected", r.status_code == 201, f"create={r.status_code}")

        # T08: accounting period lifecycle is audited
        r = await c.post("/api/v1/periods", headers=mgr, json={
            "period_name": f"AUDIT-{ids['org'].hex[:6]}", "start_date": "1999-01-01", "end_date": "1999-01-31"})
        pid = r.json()["id"]
        await c.patch(f"/api/v1/periods/{pid}/status", headers=mgr, json={"status": "CLOSED"})
        await c.patch(f"/api/v1/periods/{pid}/status", headers=mgr, json={"status": "OPEN", "reason": "audit reopen"})
        rows = await scalar("SELECT count(*) FROM audit_logs WHERE entity_id = :p", p=pid)
        reason_rows = await scalar("SELECT count(*) FROM audit_logs WHERE entity_id = :p AND reason = 'audit reopen'", p=pid)
        report("T08", "period create/close/reopen audited", rows < 3 or reason_rows < 1,
               f"audit rows={rows} rows with reopen reason={reason_rows}")

        # Decision items (informational only)
        r = await create(mgr, transaction_type="BANK_CHARGE", amount=Decimal("10.00"), currency="USD",
                         payment_account_id=str(ids["pa"]))
        report("D2", "non-IDR currency accepted without FX", r.status_code == 201, f"create={r.status_code}", decision=True)
        r = await create(op, transaction_type="DIRECT_PURCHASE", amount=Decimal("50.00"),
                         project_id=str(ids["project"]), cost_category="MAT")
        report("D3", "cash credit without payment account accepted", r.status_code == 201,
               f"create={r.status_code}", decision=True)

        imbalance = await scalar(
            """SELECT coalesce(sum(jl.debit_amount),0) - coalesce(sum(jl.credit_amount),0) FROM journal_lines jl
               JOIN journal_entries je ON je.id = jl.journal_entry_id WHERE je.organization_id = :o""", o=ids["org"])
        report("INV", "trial balance debit == credit", imbalance != 0, f"debit-credit={imbalance}")

    defects = [row for row in RESULTS if row[1] == "DEFECT"]
    print(f"\n{len(defects)} in-scope defect(s) present: {sorted({row[0] for row in defects})}")
    return 1 if defects else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
