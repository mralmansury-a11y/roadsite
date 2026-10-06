import os, sqlite3, secrets
from functools import wraps
from flask import (Flask, g, render_template, request, redirect, url_for,
                   session, flash, abort)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret")
DB = os.path.join(app.root_path, "site.db")
KINDS = {"news": "الأخبار", "services": "الخدمات"}
SITE = {"name": "إدارة خدمات الطريق الدولي", "en": "INTERNATIONAL ROAD SERVICES",
        "phone": "+218 91 711 5907", "email": "info@iroad.ly",
        "address": "سرت، ليبيا"}  # عدّل بياناتك الحقيقية هنا


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_=None):
    d = g.pop("db", None)
    if d:
        d.close()


def init_db():
    c = sqlite3.connect(DB)
    c.executescript("""
    create table if not exists admins(id integer primary key, username text unique, pw text);
    create table if not exists messages(id integer primary key, name text, email text, phone text,
        subject text, body text, created text default current_timestamp, is_read integer default 0);
    create table if not exists news(id integer primary key, title text, body text, created text default current_timestamp);
    create table if not exists services(id integer primary key, title text, body text);""")
    if not c.execute("select 1 from admins").fetchone():
        c.execute("insert into admins(username,pw) values(?,?)",
                  ("admin", generate_password_hash(os.environ.get("ADMIN_PASSWORD", "admin123"))))
    if not c.execute("select 1 from services").fetchone():
        c.executemany("insert into services(title,body) values(?,?)", [
            ("الصيانة والطوارئ", "صيانة دورية للطريق والاستجابة السريعة للحوادث والأعطال."),
            ("السلامة المرورية", "لوحات إرشادية وعلامات تحذيرية وإجراءات تضمن سلامة مستخدمي الطريق."),
            ("المراقبة والتفتيش", "متابعة ميدانية مستمرة لحالة الطريق ومرافقه وجودة الخدمات."),
            ("الإنارة والنظافة", "تأمين الإنارة الليلية وصيانة المرافق والمحافظة على نظافة الطريق.")])
    c.commit()
    c.close()


@app.before_request
def csrf():
    session.setdefault("csrf", secrets.token_hex(16))
    if request.method == "POST" and request.form.get("csrf") != session["csrf"]:
        abort(400)


@app.context_processor
def inject():
    return {"site": SITE, "csrf": session.get("csrf")}


def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return f(*a, **k)
    return w


# ---------- الموقع العام ----------
@app.route("/")
def home():
    q = db().execute
    return render_template("index.html", services=q("select * from services limit 4").fetchall(),
                           news=q("select * from news order by id desc limit 3").fetchall())


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/services")
def services():
    return render_template("services.html", rows=db().execute("select * from services").fetchall())


@app.route("/news")
def news():
    return render_template("news.html", rows=db().execute("select * from news order by id desc").fetchall())


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        f = {k: request.form.get(k, "").strip()[:2000] for k in ("name", "email", "phone", "subject", "body")}
        if f["name"] and f["body"] and (f["email"] or f["phone"]):
            db().execute("insert into messages(name,email,phone,subject,body) values(?,?,?,?,?)", tuple(f.values()))
            db().commit()
            flash("تم إرسال رسالتك بنجاح، سنتواصل معك قريبًا.")
            return redirect(url_for("contact"))
        flash("يرجى تعبئة الاسم والرسالة ووسيلة تواصل واحدة على الأقل.")
    return render_template("contact.html")


# ---------- لوحة الإدارة ----------
@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = db().execute("select * from admins where username=?", (request.form.get("username", ""),)).fetchone()
        if u and check_password_hash(u["pw"], request.form.get("password", "")):
            session["admin"] = u["id"]
            return redirect(url_for("dashboard"))
        flash("بيانات الدخول غير صحيحة.")
    return render_template("login.html")


@app.route("/admin/logout", methods=["POST"])
def logout():
    session.pop("admin", None)
    return redirect(url_for("home"))


@app.route("/admin")
@login_required
def dashboard():
    q = db().execute
    stats = {k: q(f"select count(*) from {k}").fetchone()[0] for k in ("messages", "news", "services")}
    stats["unread"] = q("select count(*) from messages where is_read=0").fetchone()[0]
    return render_template("admin.html", stats=stats,
                           msgs=q("select * from messages order by id desc").fetchall())


@app.route("/admin/<kind>", methods=["GET", "POST"])
@login_required
def items(kind):
    if kind not in KINDS:
        abort(404)
    if request.method == "POST":
        t, b, i = request.form["title"].strip(), request.form["body"].strip(), request.form.get("id")
        if t and b:
            if i:
                db().execute(f"update {kind} set title=?,body=? where id=?", (t, b, i))
            else:
                db().execute(f"insert into {kind}(title,body) values(?,?)", (t, b))
            db().commit()
            flash("تم الحفظ.")
        return redirect(url_for("items", kind=kind))
    rows = db().execute(f"select * from {kind} order by id desc").fetchall()
    edit = db().execute(f"select * from {kind} where id=?", (request.args["edit"],)).fetchone() if request.args.get("edit") else None
    return render_template("admin_items.html", kind=kind, label=KINDS[kind], rows=rows, edit=edit)


@app.route("/admin/<kind>/<int:i>/delete", methods=["POST"])
@login_required
def delete(kind, i):
    if kind not in (*KINDS, "messages"):
        abort(404)
    db().execute(f"delete from {kind} where id=?", (i,))
    db().commit()
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/admin/messages/<int:i>/read", methods=["POST"])
@login_required
def read(i):
    db().execute("update messages set is_read=1 where id=?", (i,))
    db().commit()
    return redirect(url_for("dashboard"))


import click, getpass

@app.cli.command("set-admin")
def set_admin():
    """تغيير اسم مستخدم وكلمة مرور المدير"""
    old = input("اسم المستخدم الحالي [admin]: ") or "admin"
    new = input("اسم المستخدم الجديد: ").strip()
    pw = getpass.getpass("كلمة المرور الجديدة: ")
    if not new or len(pw) < 10:
        raise click.ClickException("اسم فارغ أو كلمة مرور أقل من 10 أحرف")
    c = sqlite3.connect(DB)
    n = c.execute("update admins set username=?, pw=? where username=?",
                  (new, generate_password_hash(pw), old)).rowcount
    c.commit(); c.close()
    click.echo("تم التحديث" if n else "لم يُعثر على المستخدم")



init_db()
if __name__ == "__main__":
    app.run(debug=True)
