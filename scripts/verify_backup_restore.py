"""Verify PostgreSQL backup and restore against local Docker infrastructure."""

import subprocess
import sys


def run_docker(cmd: list[str]) -> subprocess.CompletedProcess:
    full_cmd = ["docker", "exec", "financial-saas-postgres"] + cmd
    return subprocess.run(full_cmd, capture_output=True, text=True, check=True)


def main() -> int:
    dump_path = "/tmp/financial_saas_backup_test.dump"
    restore_db = "financial_saas_restore_test"

    print("1. Taking custom-format backup of financial_saas...")
    run_docker([
        "pg_dump",
        "-U", "financial",
        "-d", "financial_saas",
        "-F", "c",
        "-f", dump_path,
    ])

    print("2. Verifying dump TOC via pg_restore --list...")
    toc = run_docker(["pg_restore", "--list", dump_path]).stdout
    if "TABLE DATA" not in toc:
        print("FAIL: Dump does not contain table data.")
        return 1

    print("3. Creating isolated test database...")
    run_docker(["dropdb", "-U", "financial", "--if-exists", restore_db])
    run_docker(["createdb", "-U", "financial", restore_db])

    try:
        print("4. Restoring dump into isolated test database...")
        run_docker([
            "pg_restore",
            "-U", "financial",
            "-d", restore_db,
            "--no-owner",
            dump_path,
        ])

        print("5. Comparing table counts between primary and restored database...")
        count_sql = "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';"
        c_orig = int(run_docker(["psql", "-U", "financial", "-d", "financial_saas", "-t", "-c", count_sql]).stdout.strip())
        c_rest = int(run_docker(["psql", "-U", "financial", "-d", restore_db, "-t", "-c", count_sql]).stdout.strip())

        print(f"   Original tables: {c_orig}, Restored tables: {c_rest}")
        if c_orig == 0 or c_orig != c_rest:
            print("FAIL: Table count mismatch.")
            return 1

        print("6. Verifying sample record counts...")
        for table in ["organizations", "users", "chart_of_accounts"]:
            tbl_sql = f"SELECT count(*) FROM {table};"
            t_orig = int(run_docker(["psql", "-U", "financial", "-d", "financial_saas", "-t", "-c", tbl_sql]).stdout.strip())
            t_rest = int(run_docker(["psql", "-U", "financial", "-d", restore_db, "-t", "-c", tbl_sql]).stdout.strip())
            print(f"   Table {table}: original={t_orig}, restored={t_rest}")
            if t_orig != t_rest:
                print(f"FAIL: Row count mismatch on table {table}")
                return 1

        print("BACKUP_RESTORE_PASS: Full logical backup and restore verified successfully.")
        return 0
    finally:
        print("7. Cleaning up isolated test database and dump file...")
        run_docker(["dropdb", "-U", "financial", "--if-exists", restore_db])
        run_docker(["rm", "-f", dump_path])


if __name__ == "__main__":
    sys.exit(main())
