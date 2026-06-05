# handlers.py
import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown
from bot.utils import (
    get_disk_space, get_ram_usage, get_cpu_usage,
    check_service, check_url_status, check_telegram_api
)
from bot.indexers import search_torrents
from bot.torrent import qb_health, qb_list_torrents, add_torrent, qb_list_pending_torrents
from bot.config import get_settings

log = logging.getLogger(__name__)

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
            f"📦 {t['size']} MB | 👥 {t['seeders']} | 🌍 `{tracker}`"
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
    qbt_api = "Online" if qb_health() else "Down"
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

    jackett_block = ""
    if jackett_status is not None:
        jackett_block = (
            "=== Jackett ===\n"
            f"WebUI/API:  {jackett_status}\n\n"
        )

    text = (
        "*System Status*\n"
        "```\n"
        "=== qBittorrent ===\n"
        f"API:       {qbt_api}\n"
        f"Downloading: {downloading}\n"
        f"Paused:      {paused}\n"
        f"Completed:   {completed}\n"
        f"Pending:     {pending_total}\n\n"
        "=== Prowlarr ===\n"
        f"WebUI/API:  {prowlarr_status}\n\n"
        f"{jackett_block}"
        "=== Telegram Bot ===\n"
        f"API:       {tg_api}\n\n"
        "=== System ===\n"
        f"Disk:      {disk}\n"
        f"RAM:       {ram}\n"
        f"CPU:       {cpu}\n"
        "```"
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

    msg = "*📋 Torrent Status*\n```"
    for t in ts:
        name = (t.get('name') or "")[:30]
        state = t.get('state')
        msg += f"{name:30} | {state}\n"
    msg += "```"
    await update.message.reply_text(msg)
