"""One-time: creates each service's own login in its own Azure SQL database.

The Azure equivalent of db/init.sql. Azure SQL databases are separate units,
so each service gets a contained user (user and password live in that
database only): it cannot even sign in to the other database. Roles are the
same as locally: DDL for its migrations, plus read and write.

Run from the repository root after infra/setup.sh, with your own IP allowed
on the server's firewall for the duration:

    python infra/create_db_users.py

Reads the passwords from infra/.secrets.local, and connects as the server
admin, which only this script and the person running it ever use. Safe to
run again: existing users get their password reset to the file's value.
"""
import sys
from pathlib import Path

import pymssql

PREFIX = "lhoffmann"
SERVER = f"{PREFIX}-sql2.database.windows.net"
SQL_ADMIN = "avdeskadmin"
SECRETS_FILE = Path(__file__).with_name(".secrets.local")
SERVICES = {"requests": "REQUESTS_DB_PASSWORD", "feedback": "FEEDBACK_DB_PASSWORD"}
ROLES = ("db_ddladmin", "db_datareader", "db_datawriter")


def read_secrets(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            name, _, value = line.partition("=")
            values[name.strip()] = value.strip()
    return values


def create_user(database: str, user: str, password: str, admin_password: str) -> None:
    # The free-offer database may be paused; the first login wakes it, which
    # can take a minute, hence the long login timeout.
    with pymssql.connect(server=SERVER, user=SQL_ADMIN, password=admin_password, database=database,
                         login_timeout=90, autocommit=True) as connection:
        cursor = connection.cursor()
        # DDL takes no parameters; the password comes from our own file and is
        # hex plus fixed letters, so it cannot break out of the quotes.
        if not password.isalnum():
            raise ValueError("Passwords must be letters and digits only")
        cursor.execute(f"""
            IF USER_ID(N'{user}') IS NULL
                CREATE USER [{user}] WITH PASSWORD = N'{password}';
            ELSE
                ALTER USER [{user}] WITH PASSWORD = N'{password}';
        """)
        for role in ROLES:
            cursor.execute(f"ALTER ROLE {role} ADD MEMBER [{user}];")
    print(f"{database}: user {user} ready")


def main() -> int:
    secrets = read_secrets(SECRETS_FILE)
    for service, password_name in SERVICES.items():
        create_user(f"{PREFIX}-{service}-db", f"avdesk_{service}", secrets[password_name],
                    secrets["SQL_ADMIN_PASSWORD"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
