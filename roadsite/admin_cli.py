"""Admin account management commands for the roadsite Flask app.

Run from the project folder with the virtualenv active:

    flask --app app admin list
    flask --app app admin create USERNAME
    flask --app app admin passwd USERNAME
    flask --app app admin rename OLD_USERNAME NEW_USERNAME
    flask --app app admin delete USERNAME [--yes]
"""
import re
import sqlite3

import click
from flask import current_app
from flask.cli import AppGroup
from werkzeug.security import generate_password_hash

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
MIN_PASSWORD_LEN = 10

admin_cli = AppGroup("admin", help="Manage admin accounts (list, create, passwd, rename, delete).")


def init_app(app, db_path):
    """Register the 'admin' command group on the Flask app."""
    app.config["ADMIN_DB"] = db_path
    app.cli.add_command(admin_cli)


# ---------- helpers ----------
def _connect():
    conn = sqlite3.connect(current_app.config["ADMIN_DB"])
    conn.row_factory = sqlite3.Row
    return conn


def _find(conn, username):
    return conn.execute("select id, username from admins where username=?", (username,)).fetchone()


def _require(conn, username):
    row = _find(conn, username)
    if not row:
        raise click.ClickException(f"User '{username}' does not exist. Run 'admin list' to see accounts.")
    return row


def _validate_username(username):
    if not USERNAME_RE.match(username):
        raise click.BadParameter(
            "Use 3-32 characters: English letters, digits, dot, dash or underscore.",
            param_hint="USERNAME")
    return username


def _ask_password(username):
    while True:
        pw = click.prompt("New password", hide_input=True, confirmation_prompt="Confirm password")
        problems = []
        if len(pw) < MIN_PASSWORD_LEN:
            problems.append(f"at least {MIN_PASSWORD_LEN} characters")
        if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
            problems.append("both letters and digits")
        if pw.lower() == username.lower():
            problems.append("must differ from the username")
        if not problems:
            return generate_password_hash(pw)
        click.secho("Weak password: " + "; ".join(problems) + ". Try again.", fg="yellow")


# ---------- commands ----------
@admin_cli.command("list")
def list_admins():
    """List all admin accounts."""
    with _connect() as conn:
        rows = conn.execute("select id, username from admins order by id").fetchall()
    if not rows:
        click.echo("No admin accounts found.")
        return
    click.echo(f"{'ID':<6}USERNAME")
    for r in rows:
        click.echo(f"{r['id']:<6}{r['username']}")
    click.echo(f"\nTotal: {len(rows)}")


@admin_cli.command("create")
@click.argument("username")
def create_admin(username):
    """Create a new admin account."""
    _validate_username(username)
    conn = _connect()
    try:
        if _find(conn, username):
            raise click.ClickException(f"User '{username}' already exists.")
        pw_hash = _ask_password(username)
        with conn:
            conn.execute("insert into admins(username, pw) values(?, ?)", (username, pw_hash))
    finally:
        conn.close()
    click.secho(f"Admin '{username}' created.", fg="green")


@admin_cli.command("passwd")
@click.argument("username")
def change_password(username):
    """Change the password of an existing admin."""
    conn = _connect()
    try:
        row = _require(conn, username)
        pw_hash = _ask_password(username)
        with conn:
            conn.execute("update admins set pw=? where id=?", (pw_hash, row["id"]))
    finally:
        conn.close()
    click.secho(f"Password for '{username}' updated.", fg="green")


@admin_cli.command("rename")
@click.argument("old_username")
@click.argument("new_username")
def rename_admin(old_username, new_username):
    """Rename an existing admin account."""
    _validate_username(new_username)
    conn = _connect()
    try:
        row = _require(conn, old_username)
        if _find(conn, new_username):
            raise click.ClickException(f"User '{new_username}' already exists.")
        with conn:
            conn.execute("update admins set username=? where id=?", (new_username, row["id"]))
    finally:
        conn.close()
    click.secho(f"Admin '{old_username}' renamed to '{new_username}'.", fg="green")


@admin_cli.command("delete")
@click.argument("username")
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
def delete_admin(username, yes):
    """Delete an admin account (the last remaining admin cannot be deleted)."""
    conn = _connect()
    try:
        row = _require(conn, username)
        total = conn.execute("select count(*) from admins").fetchone()[0]
        if total <= 1:
            raise click.ClickException("Cannot delete the last admin account. Create another one first.")
        if not yes:
            click.confirm(f"Delete admin '{username}' permanently?", abort=True)
        with conn:
            conn.execute("delete from admins where id=?", (row["id"],))
    finally:
        conn.close()
    click.secho(f"Admin '{username}' deleted.", fg="green")
