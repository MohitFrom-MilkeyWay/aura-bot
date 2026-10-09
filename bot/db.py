"""
AURA Bot - SQLite Memory & Profile System (Stage 3)
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
from contextvars import ContextVar

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_DB = BASE_DIR / "data" / "aura.db"
# Per-bot DB key (multi-bot safe under concurrent asyncio)
_db_key: ContextVar[str] = ContextVar("aura_db_key", default="default")


def use_db(key: str = "default") -> None:
    """Switch active DB for current asyncio task / update."""
    _db_key.set(key or "default")


def get_db_path() -> Path:
    key = _db_key.get() or "default"
    if key == "default":
        return _DEFAULT_DB
    safe = "".join(c for c in key if c.isalnum() or c in ("_", "-"))[:32]
    return BASE_DIR / "data" / f"aura_{safe}.db"




# Relationship levels (basic)
RELATIONSHIP_LEVELS = [
    (0, "Stranger"),
    (5, "Acquaintance"),
    (15, "Friend"),
    (30, "Close Friend"),
    (50, "Crush"),
    (80, "Girlfriend"),
    (120, "Passionate"),
    (200, "Obsessed"),
]


def get_level_name(xp: int) -> str:
    name = "Stranger"
    for threshold, level_name in RELATIONSHIP_LEVELS:
        if xp >= threshold:
            name = level_name
    return name


def get_connection() -> sqlite3.Connection:
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist"""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            character_id TEXT DEFAULT 'aura',
            language TEXT DEFAULT 'en',
            age_verified INTEGER DEFAULT 0,
            xp INTEGER DEFAULT 0,
            message_count INTEGER DEFAULT 0,
            gems INTEGER DEFAULT 20,
            daily_messages INTEGER DEFAULT 0,
            last_message_date TEXT,
            last_daily_claim TEXT,
            is_premium INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_user
        ON messages(user_id, id DESC)
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT
        )
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id TEXT NOT NULL,
            product_type TEXT DEFAULT 'bundle',
            paid_with TEXT,
            amount INTEGER DEFAULT 0,
            created_at TEXT,
            UNIQUE(user_id, product_id)
        )
    """)


    cur.execute("""
        CREATE TABLE IF NOT EXISTS affiliate_links (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            users_joined INTEGER DEFAULT 0,
            total_stars INTEGER DEFAULT 0,
            created_at TEXT,
            note TEXT DEFAULT ''
        )
    """)

    # Migrations for existing DBs
    migrations = [
        ("language", "TEXT DEFAULT 'en'"),
        ("gems", "INTEGER DEFAULT 20"),
        ("daily_messages", "INTEGER DEFAULT 0"),
        ("last_message_date", "TEXT"),
        ("last_daily_claim", "TEXT"),
        ("is_premium", "INTEGER DEFAULT 0"),
        ("active_story", "TEXT DEFAULT ''"),
        ("premium_until", "TEXT DEFAULT ''"),
        ("total_stars_spent", "INTEGER DEFAULT 0"),
        ("referred_by", "INTEGER DEFAULT 0"),
        ("referral_count", "INTEGER DEFAULT 0"),
        ("referral_claimed", "INTEGER DEFAULT 0"),
        ("login_streak", "INTEGER DEFAULT 0"),
        ("best_streak", "INTEGER DEFAULT 0"),
        ("badges", "TEXT DEFAULT '[]'"),
        ("last_active", "TEXT DEFAULT ''"),
        ("last_nudge", "TEXT DEFAULT ''"),
        ("nudge_count", "INTEGER DEFAULT 0"),
        ("affiliate_code", "TEXT DEFAULT ''"),
    ]
    for col, typedef in migrations:
        try:
            cur.execute(f"SELECT {col} FROM users LIMIT 1")
        except sqlite3.OperationalError:
            cur.execute(f"ALTER TABLE users ADD COLUMN {col} {typedef}")
            logger.info(f"Migrated: added {col} column")

    conn.commit()
    conn.close()
    logger.info(f"Database ready at {get_db_path()}")


def get_or_create_user(user_id: int, username: str = None, first_name: str = None) -> Dict[str, Any]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()

    now = datetime.utcnow().isoformat()

    if row is None:
        cur.execute(
            """INSERT INTO users (user_id, username, first_name, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, username, first_name, now, now)
        )
        conn.commit()
        cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        logger.info(f"New user created: {user_id}")

    user = dict(row)
    conn.close()
    return user


def update_user(user_id: int, **kwargs) -> None:
    if not kwargs:
        return
    conn = get_connection()
    cur = conn.cursor()
    fields = []
    values = []
    for k, v in kwargs.items():
        fields.append(f"{k} = ?")
        values.append(v)
    fields.append("updated_at = ?")
    values.append(datetime.utcnow().isoformat())
    values.append(user_id)
    cur.execute(f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?", values)
    conn.commit()
    conn.close()


def add_message(user_id: int, role: str, content: str) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (user_id, role, content, datetime.utcnow().isoformat())
    )
    # Keep only last 40 messages per user (cleanup)
    cur.execute("""
        DELETE FROM messages
        WHERE user_id = ? AND id NOT IN (
            SELECT id FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT 40
        )
    """, (user_id, user_id))
    conn.commit()
    conn.close()


def get_history(user_id: int, limit: int = 16) -> List[Dict[str, str]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT role, content FROM messages
           WHERE user_id = ?
           ORDER BY id DESC LIMIT ?""",
        (user_id, limit)
    )
    rows = cur.fetchall()
    conn.close()
    # Reverse to chronological order
    history = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    return history


def clear_history(user_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def add_xp(user_id: int, amount: int = 1) -> Dict[str, Any]:
    """Add XP and return updated user info"""
    user = get_or_create_user(user_id)
    new_xp = user["xp"] + amount
    new_count = user["message_count"] + 1
    update_user(user_id, xp=new_xp, message_count=new_count)
    user["xp"] = new_xp
    user["message_count"] = new_count
    user["level_name"] = get_level_name(new_xp)
    return user


def get_profile(user_id: int) -> Dict[str, Any]:
    user = get_or_create_user(user_id)
    user["level_name"] = get_level_name(user["xp"])
    return user


# ==================== GEMS & DAILY LIMITS (Stage 5) ====================

# Free tier limits
DAILY_FREE_MESSAGES = 25
SELFIE_GEM_COST = 2
DAILY_BONUS_GEMS = 8
STARTING_GEMS = 20


def get_today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def check_and_reset_daily(user_id: int) -> Dict[str, Any]:
    """Reset daily message counter if new day"""
    user = get_or_create_user(user_id)
    today = get_today()
    if user.get("last_message_date") != today:
        update_user(user_id, daily_messages=0, last_message_date=today)
        user["daily_messages"] = 0
        user["last_message_date"] = today
    return user


def can_send_message(user_id: int) -> tuple:
    """Returns (allowed: bool, reason: str, user: dict)"""
    user = check_and_reset_daily(user_id)
    if is_user_premium(user_id):
        return True, "premium", user
    used = user.get("daily_messages") or 0
    limit = get_config_int("daily_free_messages", DAILY_FREE_MESSAGES)
    if used < limit:
        return True, "ok", user
    gems = user.get("gems") or 0
    if gems >= 1:
        return True, "gems", user  # will spend 1 gem
    return False, "limit", user


def record_message_usage(user_id: int, use_gem: bool = False) -> Dict[str, Any]:
    user = check_and_reset_daily(user_id)
    daily = (user.get("daily_messages") or 0) + 1
    gems = user.get("gems") or 0
    updates = {"daily_messages": daily, "last_message_date": get_today()}
    if use_gem and gems >= 1:
        updates["gems"] = gems - 1
    update_user(user_id, **updates)
    return get_profile(user_id)


def spend_gems(user_id: int, amount: int) -> tuple:
    """Spend gems. Returns (success, new_balance)"""
    user = get_or_create_user(user_id)
    gems = user.get("gems") or 0
    if gems < amount:
        return False, gems
    new_bal = gems - amount
    update_user(user_id, gems=new_bal)
    return True, new_bal


def add_gems(user_id: int, amount: int) -> int:
    user = get_or_create_user(user_id)
    new_bal = (user.get("gems") or 0) + amount
    update_user(user_id, gems=new_bal)
    return new_bal


def claim_daily_bonus(user_id: int) -> tuple:
    """Returns (success, gems_added, new_balance, message, streak)"""
    from datetime import timedelta
    user = get_or_create_user(user_id)
    today = get_today()
    if user.get("last_daily_claim") == today:
        streak = user.get("login_streak") or 0
        return False, 0, user.get("gems") or 0, "Aaj ka daily bonus pehle hi le chuke ho 🎁", streak

    base = get_config_int("daily_bonus_gems", DAILY_BONUS_GEMS)
    last = (user.get("last_daily_claim") or "").strip()
    streak = user.get("login_streak") or 0

    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    if last == yesterday:
        streak = streak + 1
    else:
        streak = 1  # reset or first claim

    # Streak bonus: +1 gem per streak day (cap +15)
    streak_bonus = min(streak, 15)
    total = base + streak_bonus
    new_bal = add_gems(user_id, total)
    best = max(user.get("best_streak") or 0, streak)
    update_user(user_id, last_daily_claim=today, login_streak=streak, best_streak=best)

    msg = f"+{total} gems! (base {base} + streak bonus {streak_bonus}) 🔥\nStreak: *{streak}* days"
    return True, total, new_bal, msg, streak


# ==================== BUNDLES / PPV (Stage 5.5) ====================

def has_purchased(user_id: int, product_id: str) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM purchases WHERE user_id = ? AND product_id = ?",
        (user_id, product_id)
    )
    row = cur.fetchone()
    conn.close()
    return row is not None


def record_purchase(user_id: int, product_id: str, product_type: str = "bundle",
                    paid_with: str = "gems", amount: int = 0) -> None:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT OR IGNORE INTO purchases
               (user_id, product_id, product_type, paid_with, amount, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, product_id, product_type, paid_with, amount,
             datetime.utcnow().isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def list_user_purchases(user_id: int) -> list:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT product_id, product_type, paid_with, amount, created_at FROM purchases WHERE user_id = ?",
        (user_id,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def is_user_premium(user_id: int) -> bool:
    """Check premium flag + optional expiry date (YYYY-MM-DD or empty=lifetime)"""
    user = get_or_create_user(user_id)
    if not user.get("is_premium"):
        return False
    until = (user.get("premium_until") or "").strip()
    if not until:
        return True  # lifetime
    today = get_today()
    if until < today:
        update_user(user_id, is_premium=0, premium_until="")
        return False
    return True


def set_premium(user_id: int, days: int = 0) -> None:
    """days=0 means lifetime"""
    if days <= 0:
        update_user(user_id, is_premium=1, premium_until="")
    else:
        from datetime import timedelta
        until = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d")
        update_user(user_id, is_premium=1, premium_until=until)


def add_stars_spent(user_id: int, amount: int) -> None:
    user = get_or_create_user(user_id)
    total = (user.get("total_stars_spent") or 0) + amount
    update_user(user_id, total_stars_spent=total)
    try:
        add_affiliate_stars(user_id, int(amount or 0))
    except Exception as e:
        logger.warning(f"affiliate stars via add_stars_spent: {e}")


def get_global_stats() -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(message_count),0) FROM users")
    total_messages = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users WHERE is_premium=1")
    premium_users = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(total_stars_spent),0) FROM users")
    total_stars = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM purchases")
    total_purchases = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(amount),0) FROM purchases WHERE paid_with='stars'")
    stars_from_purchases = cur.fetchone()[0] or 0
    cur.execute("SELECT COALESCE(SUM(gems),0) FROM users")
    total_gems_held = cur.fetchone()[0]
    conn.close()
    return {
        "total_users": total_users,
        "total_messages": total_messages,
        "premium_users": premium_users,
        "total_stars_spent": total_stars,
        "total_purchases": total_purchases,
        "stars_from_purchases": stars_from_purchases,
        "total_gems_held": total_gems_held,
    }


# ==================== CONFIG (live prices / limits) ====================

def get_config(key: str, default: str = None) -> Optional[str]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM config WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0]
    return default


def set_config(key: str, value: str) -> None:
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute(
        "INSERT INTO config(key, value, updated_at) VALUES(?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, str(value), now),
    )
    conn.commit()
    conn.close()


def get_config_int(key: str, default: int) -> int:
    v = get_config(key)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def list_config() -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM config")
    rows = cur.fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


def get_recent_users(limit: int = 15) -> list:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, username, first_name, message_count, gems, is_premium, created_at "
        "FROM users ORDER BY updated_at DESC LIMIT ?",
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    cols = ["user_id", "username", "first_name", "message_count", "gems", "is_premium", "created_at"]
    return [dict(zip(cols, r)) for r in rows]


def get_top_spenders(limit: int = 10) -> list:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, username, first_name, total_stars_spent, is_premium "
        "FROM users WHERE total_stars_spent > 0 ORDER BY total_stars_spent DESC LIMIT ?",
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    cols = ["user_id", "username", "first_name", "total_stars_spent", "is_premium"]
    return [dict(zip(cols, r)) for r in rows]


def count_users() -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    n = cur.fetchone()[0]
    conn.close()
    return n


# ==================== REFERRALS (Stage 8) ====================
REFERRAL_REWARD_INVITER = 25   # gems to inviter
REFERRAL_REWARD_INVITEE = 15   # gems to new user


def apply_referral(new_user_id: int, inviter_id: int) -> tuple:
    """Apply referral once. Returns (ok, message)"""
    if not inviter_id or inviter_id == new_user_id:
        return False, "invalid"
    new_user = get_or_create_user(new_user_id)
    if new_user.get("referred_by"):
        return False, "already_referred"
    # inviter must exist
    inviter = get_or_create_user(inviter_id)
    update_user(new_user_id, referred_by=inviter_id)
    # rewards
    add_gems(new_user_id, REFERRAL_REWARD_INVITEE)
    add_gems(inviter_id, REFERRAL_REWARD_INVITER)
    inv_count = (inviter.get("referral_count") or 0) + 1
    update_user(inviter_id, referral_count=inv_count)
    return True, f"+{REFERRAL_REWARD_INVITEE} gems for you, +{REFERRAL_REWARD_INVITER} for inviter"


def get_referral_stats(user_id: int) -> dict:
    user = get_or_create_user(user_id)
    return {
        "referral_count": user.get("referral_count") or 0,
        "referred_by": user.get("referred_by") or 0,
        "reward_inviter": REFERRAL_REWARD_INVITER,
        "reward_invitee": REFERRAL_REWARD_INVITEE,
    }




# ==================== AFFILIATE / PARTNER LINKS ====================
def _slug_code(name: str) -> str:
    import re
    base = re.sub(r"[^a-zA-Z0-9]+", "", (name or "").strip())[:12].lower() or "partner"
    return base


def create_affiliate_link(name: str, note: str = "") -> dict:
    """Create partner tracking link. Returns {code, name, ...}"""
    name = (name or "").strip()[:40] or "Partner"
    note = (note or "").strip()[:120]
    base = _slug_code(name)
    code = base
    conn = get_connection()
    cur = conn.cursor()
    n = 0
    while True:
        cur.execute("SELECT 1 FROM affiliate_links WHERE code = ?", (code,))
        if not cur.fetchone():
            break
        n += 1
        code = f"{base}{n}"
    now = datetime.utcnow().isoformat()
    cur.execute(
        """INSERT INTO affiliate_links (code, name, active, users_joined, total_stars, created_at, note)
           VALUES (?, ?, 1, 0, 0, ?, ?)""",
        (code, name, now, note),
    )
    conn.commit()
    conn.close()
    return {"code": code, "name": name, "note": note, "users_joined": 0, "total_stars": 0}


def list_affiliate_links(include_inactive: bool = True) -> list:
    conn = get_connection()
    cur = conn.cursor()
    if include_inactive:
        cur.execute(
            "SELECT code, name, active, users_joined, total_stars, created_at, note "
            "FROM affiliate_links ORDER BY created_at DESC"
        )
    else:
        cur.execute(
            "SELECT code, name, active, users_joined, total_stars, created_at, note "
            "FROM affiliate_links WHERE active = 1 ORDER BY created_at DESC"
        )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_affiliate_link(code: str) -> Optional[dict]:
    if not code:
        return None
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT code, name, active, users_joined, total_stars, created_at, note "
        "FROM affiliate_links WHERE code = ?",
        (code,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def set_affiliate_active(code: str, active: bool) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE affiliate_links SET active = ? WHERE code = ?", (1 if active else 0, code))
    ok = cur.rowcount > 0
    conn.commit()
    conn.close()
    return ok


def apply_affiliate(new_user_id: int, code: str) -> tuple:
    """Attribute first-touch affiliate. Returns (ok, message)."""
    code = (code or "").strip().lower()
    if not code:
        return False, "empty"
    link = get_affiliate_link(code)
    if not link or not link.get("active"):
        return False, "invalid"
    user = get_or_create_user(new_user_id)
    if (user.get("affiliate_code") or "").strip():
        return False, "already"
    update_user(new_user_id, affiliate_code=code)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE affiliate_links SET users_joined = users_joined + 1 WHERE code = ?",
        (code,),
    )
    conn.commit()
    conn.close()
    return True, link.get("name") or code


def add_affiliate_stars(user_id: int, stars: int) -> None:
    """Add stars revenue to the affiliate who brought this user."""
    if not stars or stars <= 0:
        return
    user = get_or_create_user(user_id)
    code = (user.get("affiliate_code") or "").strip()
    if not code:
        return
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE affiliate_links SET total_stars = total_stars + ? WHERE code = ?",
        (int(stars), code),
    )
    conn.commit()
    conn.close()


def get_affiliate_detail(code: str) -> dict:
    link = get_affiliate_link(code)
    if not link:
        return {}
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, first_name, username, total_stars_spent, message_count, created_at "
        "FROM users WHERE affiliate_code = ? ORDER BY created_at DESC LIMIT 30",
        (code,),
    )
    users = [dict(r) for r in cur.fetchall()]
    conn.close()
    link["users"] = users
    return link


# ==================== BADGES & STREAKS (Stage 9) ====================
BADGE_DEFS = {
    "first_chat": {"title": "First Words", "emoji": "💬", "desc": "Send your first message"},
    "chat_50": {"title": "Talkative", "emoji": "🗣️", "desc": "50 messages"},
    "chat_200": {"title": "Addicted", "emoji": "🔥", "desc": "200 messages"},
    "xp_50": {"title": "Crush Zone", "emoji": "💘", "desc": "Reach 50 XP"},
    "xp_120": {"title": "Girlfriend", "emoji": "💕", "desc": "Reach 120 XP"},
    "streak_3": {"title": "3-Day Flame", "emoji": "🕯️", "desc": "3-day login streak"},
    "streak_7": {"title": "Week Warrior", "emoji": "🏆", "desc": "7-day login streak"},
    "streak_30": {"title": "Monthly Devotion", "emoji": "👑", "desc": "30-day streak"},
    "referral_1": {"title": "Wingman", "emoji": "🤝", "desc": "Invite 1 friend"},
    "referral_5": {"title": "Recruiter", "emoji": "📣", "desc": "Invite 5 friends"},
    "buyer": {"title": "Supporter", "emoji": "💎", "desc": "Make any purchase"},
    "premium": {"title": "VIP", "emoji": "👑", "desc": "Activate Premium"},
    "story_1": {"title": "Roleplayer", "emoji": "🎬", "desc": "Start a storyline"},
}


def get_badges(user_id: int) -> list:
    user = get_or_create_user(user_id)
    raw = user.get("badges") or "[]"
    try:
        data = json.loads(raw) if isinstance(raw, str) else (raw or [])
        return list(data) if isinstance(data, list) else []
    except Exception:
        return []


def save_badges(user_id: int, badges: list) -> None:
    update_user(user_id, badges=json.dumps(badges))


def award_badge(user_id: int, badge_id: str) -> Optional[dict]:
    """Award badge if not owned. Returns badge def or None"""
    if badge_id not in BADGE_DEFS:
        return None
    owned = get_badges(user_id)
    if badge_id in owned:
        return None
    owned.append(badge_id)
    save_badges(user_id, owned)
    return BADGE_DEFS[badge_id]


def check_and_award_badges(user_id: int) -> list:
    """Check milestones and award new badges. Returns list of newly awarded defs."""
    user = get_profile(user_id)
    newly = []
    msg_count = user.get("message_count") or 0
    xp = user.get("xp") or 0
    streak = user.get("login_streak") or 0
    refs = user.get("referral_count") or 0
    purchases = list_user_purchases(user_id)
    is_prem = is_user_premium(user_id)
    story = (user.get("active_story") or "").strip()

    checks = []
    if msg_count >= 1:
        checks.append("first_chat")
    if msg_count >= 50:
        checks.append("chat_50")
    if msg_count >= 200:
        checks.append("chat_200")
    if xp >= 50:
        checks.append("xp_50")
    if xp >= 120:
        checks.append("xp_120")
    if streak >= 3:
        checks.append("streak_3")
    if streak >= 7:
        checks.append("streak_7")
    if streak >= 30:
        checks.append("streak_30")
    if refs >= 1:
        checks.append("referral_1")
    if refs >= 5:
        checks.append("referral_5")
    if purchases:
        checks.append("buyer")
    if is_prem:
        checks.append("premium")
    if story:
        checks.append("story_1")

    for bid in checks:
        awarded = award_badge(user_id, bid)
        if awarded:
            newly.append(awarded)
    return newly


def format_badges_text(user_id: int) -> str:
    owned = get_badges(user_id)
    if not owned:
        return "_Abhi koi badge nahi – baat karo, daily claim karo!_"
    lines = []
    for bid in owned:
        b = BADGE_DEFS.get(bid)
        if b:
            lines.append(f"{b['emoji']} *{b['title']}* – {b['desc']}")
    # locked hints
    locked = [bid for bid in BADGE_DEFS if bid not in owned]
    if locked and len(lines) < 8:
        lines.append("\n_Locked:_ " + ", ".join(BADGE_DEFS[b]["emoji"] for b in locked[:6]) + "...")
    return "\n".join(lines)


def touch_activity(user_id: int) -> None:
    """Mark user as active now (ISO utc) and reset nudge spam counter"""
    now = datetime.utcnow().isoformat()
    update_user(user_id, last_active=now, nudge_count=0)


def get_users_for_nudge(idle_seconds: int = 120, nudge_cooldown_seconds: int = 1800) -> list:
    """Users idle >= idle_seconds, not nudged within cooldown, age-ish active."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT user_id, last_active, last_nudge, character_id, language, nudge_count
           FROM users
           WHERE last_active IS NOT NULL AND last_active != ''
             AND age_verified = 1"""
    )
    rows = cur.fetchall()
    conn.close()
    now = datetime.utcnow()
    out = []
    for row in rows:
        d = dict(row)
        try:
            la = datetime.fromisoformat(d["last_active"])
        except Exception:
            continue
        idle = (now - la).total_seconds()
        if idle < idle_seconds:
            continue
        ln = (d.get("last_nudge") or "").strip()
        if ln:
            try:
                ln_dt = datetime.fromisoformat(ln)
                if (now - ln_dt).total_seconds() < nudge_cooldown_seconds:
                    continue
            except Exception:
                pass
        # max 3 nudges per idle session-ish – reset when user comes back via touch
        if (d.get("nudge_count") or 0) >= 5:
            continue
        out.append(d)
    return out


def mark_nudged(user_id: int) -> None:
    user = get_or_create_user(user_id)
    cnt = (user.get("nudge_count") or 0) + 1
    update_user(user_id, last_nudge=datetime.utcnow().isoformat(), nudge_count=cnt)


def reset_nudge_count(user_id: int) -> None:
    update_user(user_id, nudge_count=0)
