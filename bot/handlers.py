# handlers.py
import os
import asyncio
import logging
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown
from bot.utils import (
    get_disk_space, get_ram_usage, get_cpu_usage,
    check_service, check_url_status, check_telegram_api
)
from bot.indexers import search_torrents
from bot.torrent import (
    add_torrent,
    qb_get_preferences,
    qb_health,
    qb_list_pending_torrents,
    qb_list_torrents,
)
from bot.config import get_settings
from bot.media import (
    MEDIA_CATEGORIES,
    MediaEntry,
    MediaError,
    delete_media_entry,
    format_bytes,
    list_media_entries,
)
from bot.vpn import get_vpn_info

log = logging.getLogger(__name__)

MEDIA_PAGE_SIZE = 5
MEGABYTES_PER_GIGABYTE = 1000


def format_torrent_size(size_mb: int | float) -> str:
    """Format a torrent size for search result cards."""
    if size_mb >= MEGABYTES_PER_GIGABYTE:
        size_gb = size_mb / MEGABYTES_PER_GIGABYTE
        formatted_gb = f"{size_gb:.2f}".rstrip("0").rstrip(".")
        return f"{formatted_gb} GB"
    return f"{size_mb:g} MB"

def _allowed(chat_type: str, chat_id: int, user_id: int) -> bool:
    """Gate all handlers; log why we block."""
    s = get_settings()
    ok = True
    if chat_type == "private":
        ok = (user_id == s.authorized_user_id)
    elif chat_type in ("group", "supergroup"):
        ok = (chat_id == s.allowed_chat_id)
    else:
        ok = False
    if not ok:
        log.debug(f"[BLOCKED] chat_type={chat_type} chat_id={chat_id} user_id={user_id} "
                  f"env(AUTH_USER={s.authorized_user_id}, ALLOWED_CHAT={s.allowed_chat_id})")
    return ok

# Store pending magnet per-user via PTB user_data

async def send_search_page(msg, context):
    page = context.user_data.get("search_page", 0)
    results = context.user_data.get("search_results", [])
    per = 5
    total = len(results)
    pages = (total + per - 1) // per
    start = page * per
    subset = results[start:start+per]
    chat_type = msg.message.chat.type
    delay = 0.1 if chat_type == "private" else 1.0  # slower for groups to avoid flood limits
    log.debug(f"[SEARCH PAGE] page={page+1}/{pages} chat_type={chat_type} delay={delay}s total={total}")

    for i, t in enumerate(subset, start=start):
        title = escape_markdown(str(t.get('title', '')), version=1)
        tracker = escape_markdown(str(t.get('tracker', '')), version=1)
        text = (
            f"🎬 *{i+1}. {title}*\n"
            f"📦 {format_torrent_size(t['size'])} | 👥 {t['seeders']} | 🌍 `{tracker}`"
        )
        await msg.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔗 Get Magnet", callback_data=f"magnet_{i}")]]
            )
        )
        await asyncio.sleep(delay)

    # navigation with page/total info
    kb = []
    if page > 0:
        kb.append(InlineKeyboardButton("⬆️ Prev", callback_data="page_prev"))
    if start + per < total:
        kb.append(InlineKeyboardButton("⬇️ Next", callback_data="page_next"))
    info = f"Page {page+1}/{pages} ({total} results)"
    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton(info, callback_data="noop")]] + ([kb] if kb else [])
    )
    await msg.message.reply_text("Navigate:", reply_markup=markup)


def _media_category_markup() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(category, callback_data=f"media:category:{category}")]
        for category in MEDIA_CATEGORIES
    ]
    return InlineKeyboardMarkup(rows)


async def handle_media_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the media browser from the Telegram command menu."""
    chat = update.effective_chat
    user = update.effective_user
    if not _allowed(chat.type, chat.id, user.id):
        return

    await update.message.reply_text(
        "Choose a media folder:",
        reply_markup=_media_category_markup(),
    )


def _media_kind_label(entry: MediaEntry) -> str:
    return {
        "file": "File",
        "folder": "Folder",
        "symlink": "Link",
    }.get(entry.kind, "Item")


def _truncate_media_name(value: object, limit: int = 32) -> str:
    name = " ".join(str(value or "Unnamed item").split()) or "Unnamed item"
    return name if len(name) <= limit else f"{name[:limit - 1].rstrip()}..."


def _media_listing(context: ContextTypes.DEFAULT_TYPE, token: str):
    listing = context.user_data.get("media_listing")
    if not isinstance(listing, dict) or listing.get("token") != token:
        return None
    return listing


def _media_item_from_callback(context, token: str, index: str):
    listing = _media_listing(context, token)
    if listing is None:
        return None, None
    try:
        position = int(index)
    except (TypeError, ValueError):
        return None, None

    entries = listing.get("entries", [])
    if not 0 <= position < len(entries):
        return None, None
    return listing, entries[position]


def _media_action_markup(token: str, index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Delete", callback_data=f"media:delete:{token}:{index}"),
            InlineKeyboardButton("Cancel", callback_data=f"media:cancel:{token}:{index}"),
        ]
    ])


async def _render_media_page(query, context, notice: str | None = None):
    listing = context.user_data.get("media_listing")
    if not isinstance(listing, dict):
        await query.edit_message_text("This media menu expired. Use /mediafiles again.")
        return

    category = listing.get("category", "Unknown")
    entries = listing.get("entries", [])
    page = max(0, int(listing.get("page", 0)))
    total = len(entries)
    pages = max(1, (total + MEDIA_PAGE_SIZE - 1) // MEDIA_PAGE_SIZE)
    page = min(page, pages - 1)
    listing["page"] = page

    start = page * MEDIA_PAGE_SIZE
    subset = entries[start:start + MEDIA_PAGE_SIZE]
    lines = [
        f"*Media files — {escape_markdown(str(category), version=1)}*",
        f"Page {page + 1}/{pages} ({total} items)",
    ]
    if notice:
        lines.extend(["", escape_markdown(notice, version=1)])

    keyboard = []
    if subset:
        for position, entry in enumerate(subset, start=start):
            name = escape_markdown(entry.name, version=1)
            lines.extend([
                "",
                f"*{position + 1}. {name}*",
                f"Type: {_media_kind_label(entry)}",
                f"Size: {format_bytes(entry.size_bytes)}",
            ])
            keyboard.append([
                InlineKeyboardButton(
                    f"Select {position + 1}: {_truncate_media_name(entry.name)}",
                    callback_data=f"media:select:{listing['token']}:{position}",
                )
            ])
    else:
        lines.extend(["", "No files or folders found."])

    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                "Prev",
                callback_data=f"media:page:{listing['token']}:{page - 1}",
            )
        )
    if page + 1 < pages:
        navigation.append(
            InlineKeyboardButton(
                "Next",
                callback_data=f"media:page:{listing['token']}:{page + 1}",
            )
        )
    if navigation:
        keyboard.append(navigation)
    keyboard.append([
        InlineKeyboardButton("Choose another folder", callback_data="media:categories")
    ])

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _load_media_category(query, context, category: str, notice: str | None = None):
    try:
        entries = await asyncio.to_thread(list_media_entries, category)
    except MediaError as exc:
        await query.edit_message_text(
            f"Could not read {escape_markdown(category, version=1)}: "
            f"{escape_markdown(str(exc), version=1)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Choose another folder", callback_data="media:categories")]
            ]),
        )
        return

    context.user_data["media_listing"] = {
        "token": uuid.uuid4().hex[:12],
        "category": category,
        "entries": entries,
        "page": 0,
    }
    await _render_media_page(query, context, notice=notice)


async def handle_media_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle media browsing and destructive actions separately from torrent callbacks."""
    query = update.callback_query
    await query.answer()
    chat = query.message.chat
    uid = query.from_user.id
    if not _allowed(chat.type, chat.id, uid):
        return

    data = query.data or ""
    if data == "media:categories":
        await query.edit_message_text(
            "Choose a media folder:",
            reply_markup=_media_category_markup(),
        )
        return

    if data.startswith("media:category:"):
        category = data.split(":", 2)[2]
        if category not in MEDIA_CATEGORIES:
            await query.edit_message_text("Invalid media folder.")
            return
        await _load_media_category(query, context, category)
        return

    parts = data.split(":")
    if len(parts) != 4 or parts[0] != "media":
        await query.edit_message_text("Invalid media selection.")
        return

    action, token, index_text = parts[1:]

    if action == "page":
        listing = _media_listing(context, token)
        if listing is None:
            await query.edit_message_text("This media menu expired. Use /mediafiles again.")
            return
        try:
            listing["page"] = max(0, int(index_text))
        except (TypeError, ValueError):
            await query.edit_message_text("Invalid media page.")
            return
        await _render_media_page(query, context)
        return

    listing, entry = _media_item_from_callback(context, token, index_text)
    if listing is None or entry is None:
        await query.edit_message_text("This media menu expired. Use /mediafiles again.")
        return

    try:
        index = int(index_text)
    except (TypeError, ValueError):
        await query.edit_message_text("Invalid media selection.")
        return

    if action == "select":
        warning = "This will permanently delete the folder and all its contents." if entry.kind == "folder" else "This deletion is permanent."
        text = (
            f"*{escape_markdown(entry.name, version=1)}*\n"
            f"Type: {_media_kind_label(entry)}\n"
            f"Size: {format_bytes(entry.size_bytes)}\n\n"
            f"{warning}\nDelete this item?"
        )
        await query.edit_message_text(
            text,
            reply_markup=_media_action_markup(token, index),
        )
        return

    if action == "cancel":
        await _render_media_page(query, context)
        return

    if action == "delete":
        category = listing.get("category")
        try:
            deleted = await asyncio.to_thread(
                delete_media_entry,
                category,
                entry.relative_path,
            )
        except MediaError as exc:
            await query.edit_message_text(
                f"Could not delete {escape_markdown(entry.name, version=1)}.\n"
                f"{escape_markdown(str(exc), version=1)}",
                reply_markup=_media_action_markup(token, index),
            )
            return

        await _load_media_category(
            query,
            context,
            category,
            notice=f"Deleted {_media_kind_label(deleted).lower()}: {entry.name}",
        )
        return

    await query.edit_message_text("Invalid media action.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    if not _allowed(chat.type, chat.id, user.id):
        return

    text = (update.message.text or "").strip()
    log.debug(f"[MESSAGE] from uid={user.id} chat={chat.id} type={chat.type} text={text[:60]}")

    if text.startswith("magnet:"):
        context.user_data['pending'] = text
        kb = [[InlineKeyboardButton(c, callback_data=c)] for c in ("Movie", "TV", "Others")]
        await update.message.reply_text("Choose category:", reply_markup=InlineKeyboardMarkup(kb))
        return

    results = search_torrents(text)
    if not results:
        await update.message.reply_text("😕 No torrents found.")
        return

    context.user_data['search_results'] = results
    context.user_data['search_page'] = 0
    await send_search_page(update, context)

async def handle_category_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    chat = q.message.chat
    uid = q.from_user.id
    if not _allowed(chat.type, chat.id, uid):
        return

    if data == "noop":
        return

    if data in ("page_prev", "page_next"):
        context.user_data["search_page"] += 1 if data == "page_next" else -1
        await q.message.delete()
        await send_search_page(q, context)
        return

    if data.startswith("magnet_"):
        index = int(data.split("_")[1])
        results = context.user_data.get("search_results", [])
        if 0 <= index < len(results):
            context.user_data['pending_magnet'] = results[index]["magnet"]
            kb = [[InlineKeyboardButton(c, callback_data=c)] for c in ("Movie", "TV", "Others")]
            await q.edit_message_text("Select category:", reply_markup=InlineKeyboardMarkup(kb))
        else:
            await q.edit_message_text("Invalid selection.")
        return

    # Add torrent
    magnet = context.user_data.get('pending_magnet')
    if not magnet:
        await q.edit_message_text("No magnet link.")
        return

    if not add_torrent(magnet, data):
        await q.edit_message_text("❌ qBittorrent login failed.")
        return

    await q.edit_message_text(f"✅ Added as *{data}*")
    context.user_data.pop('pending_magnet', None)
    context.user_data.pop('pending', None)

async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    uid = update.effective_user.id
    if not _allowed(chat.type, chat.id, uid):
        return

    s = get_settings()
    qbt_api = "✅ Online" if qb_health() else "❌ Down"
    downloading = paused = completed = 0
    torrents = qb_list_torrents()
    for torrent in torrents:
        state = torrent.get("state")
        if state == "downloading":
            downloading += 1
        if state == "pausedUP":
            paused += 1
        if torrent.get("progress", 0) == 1.0:
            completed += 1

    pending_total = qb_list_pending_torrents(limit=None, count_only=True)
    if pending_total is None:
        pending_total = 0

    prowlarr_status = check_url_status(s.prowlarr_url)
    jackett_status = check_url_status(s.jackett_url) if s.jackett_api_key else None
    tg_api = check_telegram_api(s.bot_token)
    disk = get_disk_space()
    ram = get_ram_usage()
    cpu = get_cpu_usage()
    vpn = get_vpn_info()
    qb_preferences = qb_get_preferences()

    vpn_state = vpn.get("status")
    if vpn_state == "running":
        vpn_status = "✅ Running"
    elif vpn_state:
        vpn_status = f"⚠️ {str(vpn_state).capitalize()}"
    else:
        vpn_status = "⚪ Unavailable"

    peer_port = qb_preferences.get("listen_port")
    peer_port_text = str(peer_port) if isinstance(peer_port, int) and peer_port > 0 else "Unknown"
    forwarded_port = vpn.get("forwarded_port")
    forwarded_port_text = f"✅ {forwarded_port}" if forwarded_port else "⚠️ Not forwarded"
    vpn_ip = vpn.get("public_ip") or "Unavailable"
    interface = qb_preferences.get("current_network_interface") or "Default"

    jackett_block = ""
    if jackett_status is not None:
        jackett_block = (
            f"• Jackett — {jackett_status}\n"
        )

    text = (
        "*📊 System Status*\n\n"
        "*Services*\n"
        f"• qBittorrent — {qbt_api}\n"
        f"• VPN — {vpn_status}\n"
        f"• Prowlarr — {prowlarr_status}\n"
        f"{jackett_block}"
        f"• Telegram Bot — {tg_api}\n\n"
        "*Downloads*\n"
        f"⬇️ Downloading: {downloading}   ⏸ Paused: {paused}\n"
        f"✅ Completed: {completed}   ⏳ Pending: {pending_total}\n\n"
        "*🔒 VPN Routing*\n"
        "qBittorrent traffic is routed through the VPN.\n"
        f"🌐 Public IP: `{vpn_ip}`\n"
        f"🔌 Peer port: `{peer_port_text}` on `{interface}`\n"
        f"↪️ Port forwarding: {forwarded_port_text}\n\n"
        "*System*\n"
        f"💾 {disk}\n"
        f"🧠 {ram}\n"
        f"⚙️ {cpu}"
    )
    await update.message.reply_text(text)
    return

    # qB stats (simple counters)
    qbt_status = "✅ Connected"
    downloading = paused = completed = 0
    torrents = qb_list_torrents()
    for t in torrents:
        state = t.get('state')
        if state == 'downloading':
            downloading += 1
        if state == 'pausedUP':
            paused += 1
        if t.get('progress', 0) == 1.0:
            completed += 1

    # NEW: pending / not-started count only
    pending_total = qb_list_pending_torrents(limit=None, count_only=True)
    if pending_total is None:
        pending_total = 0
    pending_block = f"⏳ Pending / Not started: {pending_total}\n\n"

    # services
    jackett_webui = check_url_status("http://127.0.0.1:9117")
    jackett_service = check_service("jackett")
    s = get_settings()
    tg_api = check_telegram_api(s.bot_token)
    tg_service = check_service("telegrambot")
    plex_service = check_service(s.plex_service_name)

    # system
    disk = get_disk_space()
    ram = get_ram_usage()
    cpu = get_cpu_usage()

    text = (
        "*📊 System Status*\n"
        "```\n"
        "=== qBittorrent ===\n"
        f"🔌 {qbt_status}\n"
        f"⬇️ Downloading: {downloading}\n"
        f"⏸️ Paused:      {paused}\n"
        f"✅ Completed:   {completed}\n"
        f"{pending_block}"
        "=== Jackett ===\n"
        f"🌐 WebUI:   {jackett_webui}\n"
        f"🧲 Service: {jackett_service}\n\n"
        "=== Plex ===\n"
        f"🎞️ Service: {plex_service}\n\n"
        "=== Telegram Bot ===\n"
        f"📡 API:     {tg_api}\n"
        f"🛎️ Service: {tg_service}\n\n"
        "=== System ===\n"
        f"💽 Disk:     {disk}\n"
        f"🧠 RAM:      {ram}\n"
        f"⚙️ CPU:      {cpu}\n"
        "```"
    )
    await update.message.reply_text(text)

async def handle_tstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    uid = update.effective_user.id
    if not _allowed(chat.type, chat.id, uid):
        return

    ts = qb_list_torrents()
    if not ts:
        await update.message.reply_text("No torrents or failed to fetch.")
        return

    active = queued = completed = 0
    cards = []
    for torrent in ts:
        progress = _torrent_progress(torrent.get("progress", 0))
        state_label, state_emoji, category = _torrent_state(torrent.get("state"), progress)
        if category == "active":
            active += 1
        elif category == "queued":
            queued += 1
        elif category == "completed":
            completed += 1

        card = [
            _truncate_torrent_name(torrent.get("name")),
            f"{state_emoji} {state_label} · {progress * 100:.1f}%",
            _progress_bar(progress),
        ]
        if category == "active":
            card[-1] += f"  {_format_speed(torrent.get('dlspeed', 0))}"
        cards.append("\n".join(card))

    msg = "📋 Torrent Status\n\n" + "\n\n".join(cards)
    msg += f"\n\n{active} active · {queued} queued · {completed} completed"
    await update.message.reply_text(msg)


def _torrent_progress(value: object) -> float:
    """Return a qBittorrent progress value clamped to the expected range."""
    try:
        return min(max(float(value or 0), 0), 1)
    except (TypeError, ValueError):
        return 0


def _truncate_torrent_name(value: object, limit: int = 60) -> str:
    """Keep torrent names readable without letting one card dominate the message."""
    name = " ".join(str(value or "Unnamed torrent").split()) or "Unnamed torrent"
    return name if len(name) <= limit else f"{name[:limit - 1].rstrip()}…"


def _progress_bar(progress: float, length: int = 20) -> str:
    """Build a compact Unicode progress bar suitable for Telegram mobile clients."""
    filled = min(length, int(progress * length + 0.5))
    return f"{'█' * filled}{'░' * (length - filled)}"


def _torrent_state(state: object, progress: float) -> tuple[str, str, str]:
    """Map qBittorrent states to a readable label, emoji, and summary category."""
    value = str(state or "").lower()
    if value in {"error", "missingfiles"}:
        return "Error", "❌", "other"
    if progress >= 1:
        return "Completed", "✅", "completed"
    if value == "queueddl":
        return "Queued", "⏳", "queued"
    if value in {"pauseddl", "pausedup"}:
        return "Paused", "⏸️", "other"
    if value == "metadl":
        return "Fetching metadata", "🔎", "active"
    if value in {"downloading", "forceddl", "stalleddl"}:
        return "Downloading", "⬇️", "active"
    return "Unknown", "❔", "other"


def _format_speed(value: object) -> str:
    """Format a qBittorrent byte-per-second value for a compact status line."""
    try:
        speed = max(0, float(value))
    except (TypeError, ValueError):
        speed = 0

    units = ("B/s", "KB/s", "MB/s", "GB/s")
    for unit in units:
        if speed < 1024 or unit == units[-1]:
            return f"{speed:.1f} {unit}"
        speed /= 1024
    return "0.0 B/s"
