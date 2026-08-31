"""Atomic, local-only tenant bootstrap. Never expose this as an HTTP route."""

import argparse
import asyncio
import getpass

from sqlalchemy import select

from src.core.database import AsyncSessionLocal
from src.core.security import hash_password
from src.models.enums import UserRole
from src.models.organization import Organization
from src.models.user import User
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts


async def bootstrap_organization(session, *, slug, legal_name, admin_email, admin_name, admin_password):
    existing_org = await session.scalar(select(Organization).where(Organization.slug == slug))
    existing_user = await session.scalar(select(User).where(User.email == admin_email.lower()))
    if existing_org or existing_user:
        raise ValueError("Organization or admin already exists")
    organization = Organization(slug=slug, legal_name=legal_name)
    session.add(organization)
    await session.flush()
    session.add(
        User(
            organization_id=organization.id,
            email=admin_email.lower(),
            full_name=admin_name,
            password_hash=hash_password(admin_password),
            role=UserRole.ADMIN,
        )
    )
    coa_created, _ = await seed_standard_coa(session, organization.id)
    payment_accounts_created, _ = await seed_standard_payment_accounts(session, organization.id)
    return {
        "organization_id": str(organization.id),
        "coa_created": coa_created,
        "payment_accounts_created": payment_accounts_created,
    }


async def run(args):
    password = getpass.getpass("Initial admin password: ")
    async with AsyncSessionLocal() as session:
        try:
            result = await bootstrap_organization(
                session,
                slug=args.slug,
                legal_name=args.legal_name,
                admin_email=args.admin_email,
                admin_name=args.admin_name,
                admin_password=password,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    print(f"Created organization {result['organization_id']} with {result['coa_created']} COA and {result['payment_accounts_created']} payment accounts.")


def main():
    parser = argparse.ArgumentParser(description="Bootstrap one Financial SaaS tenant")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--legal-name", required=True)
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--admin-name", required=True)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
