# Cài đặt thư viện telegram và kết nối database (nếu chưa có)
!pip install -q python-telegram-bot psycopg2-binary

import os
import random
import time
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# ==============================
# CẤU HÌNH CƠ BẢN
# ==============================
TOKEN = "8957944263:AAEjBL7Ag2BFBJ8syst_NC4t3pdAse37UmY"
BOT_USERNAME = "Khuyenmaigame_bot"
ADMIN_ID = 8596266509  # ID Admin của bạn

# Chuỗi kết nối PostgreSQL từ Aiven của bạn
DATABASE_URL = "postgres://avnadmin:AVNS_UH1Z12RzbmPP02181uc@pg-732fe8-tanhusau1986-8bc8.d.aivencloud.com:28468/defaultdb?sslmode=require"

# ==============================
# QUẢN LÝ DỮ LIỆU POSTGRESQL
# ==============================
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    # Tạo bảng lưu thông tin người dùng
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            balance BIGINT DEFAULT 0,
            total_deposit BIGINT DEFAULT 0,
            bought_today INT DEFAULT 0,
            bought_week INT DEFAULT 0,
            otp VARCHAR(10),
            otp_time FLOAT DEFAULT 0
        )
    """)
    # Tạo bảng lưu kho hàng
    cur.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id SERIAL PRIMARY KEY,
            product_code VARCHAR(50),
            account_data TEXT
        )
    """)
    # Tạo bảng lưu đơn hàng
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            product VARCHAR(50),
            items TEXT,
            total BIGINT,
            time VARCHAR(50)
        )
    """)
    # Tạo bảng lưu cấu hình hệ thống (bảo trì)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key VARCHAR(50) PRIMARY KEY,
            value TEXT
        )
    """)
    cur.execute("INSERT INTO settings (key, value) VALUES ('maintenance', 'false') ON CONFLICT (key) DO NOTHING")
    conn.commit()
    cur.close()
    conn.close()

init_db()

def get_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    user = cur.fetchone()
    if not user:
        cur.execute("""
            INSERT INTO users (user_id, balance, total_deposit, bought_today, bought_week, otp, otp_time)
            VALUES (%s, 0, 0, 0, 0, NULL, 0)
        """, (user_id,))
        conn.commit()
        cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cur.fetchone()
    cur.close()
    conn.close()
    return dict(user)

def update_user_field(user_id, field, value):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f"UPDATE users SET {field} = %s WHERE user_id = %s", (value, user_id))
    conn.commit()
    cur.close()
    conn.close()

def get_maintenance():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = 'maintenance'")
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row['value'] == 'true' if row else False

def set_maintenance(status: bool):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE settings SET value = %s WHERE key = 'maintenance'", ('true' if status else 'false',))
    conn.commit()
    cur.close()
    conn.close()

PRODUCT_PRICE = 15000

# ==============================
# MENU CHÍNH
# ==============================
def main_menu():
    keyboard = [
        [
            InlineKeyboardButton("🛍️ Sản phẩm", callback_data="products"),
            InlineKeyboardButton("💳 Nạp tiền", callback_data="deposit")
        ],
        [
            InlineKeyboardButton("👤 Tài khoản / ID", callback_data="profile"),
            InlineKeyboardButton("📦 Đơn hàng", callback_data="orders")
        ],
        [
            InlineKeyboardButton("🎁 Mời bạn bè", callback_data="invite_friends"),
            InlineKeyboardButton("💬 Liên hệ", callback_data="contact")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==============================
# KIỂM TRA BẢO TRÌ
# ==============================
async def check_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if get_maintenance():
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            if update.message:
                await update.message.reply_text("🚧 Hệ thống đang trong quá trình bảo trì, vui lòng đợi quay lại sau!")
            elif update.callback_query:
                await update.callback_query.answer("🚧 Bot đang bảo trì!", show_alert=True)
            return True
    return False

# ==============================
# LỆNH /START
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_maintenance(update, context): return
    user = update.effective_user
    user_id = user.id
    get_user(user_id)

    args = context.args
    if args and args[0].startswith("ref_"):
        try:
            referrer_id = args[0].split("_")[1]
            if referrer_id != str(user_id):
                # Lưu thông tin giới thiệu nếu cần
                pass
        except:
            pass

    await update.message.reply_text(
        f"👋 Xin chào {user.first_name}!\n🎉 Chào mừng bạn đến với cửa hàng.\n👇 Vui lòng chọn chức năng:",
        reply_markup=main_menu()
    )

# ==============================
# LỆNH ADMIN: /baotri, /mo & /thongbao
# ==============================
async def turn_on_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    set_maintenance(True)
    await update.message.reply_text("🚧 **ĐÃ BẬT BẢO TRÌ!** Tất cả khách hàng hiện không thể sử dụng bot.", parse_mode="Markdown")

async def turn_off_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    set_maintenance(False)
    await update.message.reply_text("✅ **ĐÃ MỞ LẠI BOT!** Hệ thống đã hoạt động bình thường trở lại.", parse_mode="Markdown")

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    msg_parts = update.message.text.split(maxsplit=1)
    if len(msg_parts) < 2:
        await update.message.reply_text("⚠️ Sai cú pháp! Dùng: `/thongbao [Nội dung]`", parse_mode="Markdown")
        return
    
    content = msg_parts[1]
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    cur.close()
    conn.close()

    success = 0
    for u in users:
        try:
            await context.bot.send_message(chat_id=int(u['user_id']), text=f"📢 **THÔNG BÁO TỪ HỆ THỐNG:**\n\n{content}", parse_mode="Markdown")
            success += 1
        except:
            pass
    await update.message.reply_text(f"✅ Đã gửi thông báo thành công tới {success} khách hàng!")

# ==============================
# LỆNH ADMIN QUẢN LÝ KHO & TIỀN
# ==============================
async def add_stock_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, prod_code: str):
    if update.effective_user.id != ADMIN_ID: return
    parts = update.message.text.split(maxsplit=1)
    if len(parts) < 2:
        await update.message.reply_text("⚠️ Sai cú pháp! Nhập danh sách tài khoản phía sau lệnh.")
        return
    lines = [l.strip() for l in parts[1].split("\n") if l.strip()]
    
    conn = get_db_connection()
    cur = conn.cursor()
    for line in lines:
        cur.execute("INSERT INTO inventory (product_code, account_data) VALUES (%s, %s)", (prod_code, line))
    conn.commit()
    
    cur.execute("SELECT COUNT(*) FROM inventory WHERE product_code = %s", (prod_code,))
    total_stock = cur.fetchone()['count']
    cur.close()
    conn.close()

    await update.message.reply_text(f"✅ Đã thêm {len(lines)} tài khoản vào kho `{prod_code.upper()}`. Tổng kho: {total_stock}", parse_mode="Markdown")

async def add_cm88(update: Update, context: ContextTypes.DEFAULT_TYPE): await add_stock_handler(update, context, "cm88")
async def add_sc88(update: Update, context: ContextTypes.DEFAULT_TYPE): await add_stock_handler(update, context, "sc88")
async def add_c168(update: Update, context: ContextTypes.DEFAULT_TYPE): await add_stock_handler(update, context, "c168")

async def check_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    conn = get_db_connection()
    cur = conn.cursor()
    text = "📊 **THỐNG KÊ KHO HÀNG HIỆN TẠI:**\n\n"
    for code in ["cm88", "sc88", "c168"]:
        cur.execute("SELECT COUNT(*) FROM inventory WHERE product_code = %s", (code,))
        count = cur.fetchone()['count']
        text += f"• **{code.upper()}**: còn `{count}` sản phẩm\n"
    cur.close()
    conn.close()
    await update.message.reply_text(text, parse_mode="Markdown")

async def add_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    args = context.args
    if len(args) < 2: return
    target_id, amount = int(args[0]), int(args[1])
    u = get_user(target_id)
    
    new_balance = u["balance"] + amount
    new_deposit = u["total_deposit"] + amount
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = %s, total_deposit = %s WHERE user_id = %s", (new_balance, new_deposit, target_id))
    conn.commit()
    cur.close()
    conn.close()
    
    await update.message.reply_text(f"✅ Đã cộng {amount:,}đ cho `{target_id}`", parse_mode="Markdown")
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"🎉 **TÀI KHOẢN ĐÃ ĐƯỢC CỘNG TIỀN!**\nCộng: **{amount:,}đ**\n🪙 Số dư: **{new_balance:,}đ**\n\n👇 **MENU CHÍNH**",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
    except: pass

# ==============================
# XỬ LÝ NÚT BẤM (CALLBACK)
# ==============================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_maintenance(update, context): return
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    str_user_id = str(user_id)
    u_info = get_user(user_id)

    if query.data == "profile":
        keyboard = [
            [InlineKeyboardButton("🔐 Lấy mã OTP", callback_data="get_otp")],
            [InlineKeyboardButton("🔙 Quay lại Menu", callback_data="back")]
        ]
        await query.edit_message_text(
            f"🔹 **ID:** `{user_id}`\n🪙 **Số dư:** {u_info['balance']:,}đ\n📊 Mua hôm nay: {u_info['bought_today']}\n📈 Tổng nạp: {u_info['total_deposit']:,}đ",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )

    elif query.data == "get_otp":
        otp_code = f"{random.randint(0, 999999):06d}"
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET otp = %s, otp_time = %s WHERE user_id = %s", (otp_code, time.time(), user_id))
        conn.commit()
        cur.close()
        conn.close()

        keyboard = [
            [InlineKeyboardButton("🔄 Tạo mã OTP mới", callback_data="get_otp")],
            [InlineKeyboardButton("🔙 Quay lại Tài khoản", callback_data="profile")]
        ]
        await query.edit_message_text(
            f"🔐 **MÃ XÁC THỰC OTP CỦA BẠN**\n\n"
            f"Mã OTP: `{otp_code}`\n\n"
            f"⚠️ *Lưu ý: Mã có hiệu lực trong vòng 2 phút và chỉ sử dụng cho phiên giao dịch/xác thực của bạn.*",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )

    elif query.data == "products":
        conn = get_db_connection()
        cur = conn.cursor()
        inv_counts = {}
        for code in ["cm88", "sc88", "c168"]:
            cur.execute("SELECT COUNT(*) FROM inventory WHERE product_code = %s", (code,))
            inv_counts[code] = cur.fetchone()['count']
        cur.close()
        conn.close()

        keyboard = [
            [InlineKeyboardButton(f"1️⃣ CM88 — {PRODUCT_PRICE:,}đ (Còn: {inv_counts['cm88']})", callback_data="prod_cm88")],
            [InlineKeyboardButton(f"2️⃣ SC88 — {PRODUCT_PRICE:,}đ (Còn: {inv_counts['sc88']})", callback_data="prod_sc88")],
            [InlineKeyboardButton(f"3️⃣ C168 — {PRODUCT_PRICE:,}đ (Còn: {inv_counts['c168']})", callback_data="prod_c168")],
            [InlineKeyboardButton("🔙 Quay lại Menu", callback_data="back")]
        ]
        await query.edit_message_text("🛍️ **SẢN PHẨM**\nChọn sản phẩm muốn mua:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    
    elif query.data.startswith("prod_"):
        code = query.data.split("_")[1]
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM inventory WHERE product_code = %s", (code,))
        stock_count = cur.fetchone()['count']
        cur.close()
        conn.close()

        keyboard = []
        if stock_count > 0 and u_info['balance'] >= PRODUCT_PRICE:
            keyboard.append([InlineKeyboardButton(f"🛒 Xác nhận mua ({PRODUCT_PRICE:,}đ)", callback_data=f"buy_{code}_1")])
        elif stock_count > 0 and u_info['balance'] < PRODUCT_PRICE:
            keyboard.append([InlineKeyboardButton("❌ Không đủ số dư - Nạp tiền ngay", callback_data="deposit")])
        else:
            keyboard.append([InlineKeyboardButton("❌ Sản phẩm đã hết hàng", callback_data="products")])
            
        keyboard.append([InlineKeyboardButton("🔙 Quay lại", callback_data="products")])
        
        status_text = (
            f"🛍️ **SẢN PHẨM: {code.upper()}**\n"
            f"📦 Tồn kho: `{stock_count}` tài khoản\n"
            f"💰 Giá bán: `{PRODUCT_PRICE:,}đ`\n"
            f"🪙 Số dư của bạn: `{u_info['balance']:,}đ`"
        )
        await query.edit_message_text(status_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif query.data.startswith("buy_"):
        parts = query.data.split("_")
        code, qty = parts[1], int(parts[2])
        total_p = qty * PRODUCT_PRICE

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, account_data FROM inventory WHERE product_code = %s LIMIT %s", (code, qty))
        rows = cur.fetchall()

        if len(rows) < qty or u_info['balance'] < total_p:
            cur.close()
            conn.close()
            await query.edit_message_text("❌ Giao dịch không hợp lệ hoặc số dư thay đổi đột xuất!", reply_markup=main_menu())
            return

        items = []
        ids_to_delete = []
        for r in rows:
            items.append(r['account_data'])
            ids_to_delete.append(r['id'])

        # Xóa các tài khoản đã mua ra khỏi kho
        cur.execute("DELETE FROM inventory WHERE id = ANY(%s)", (ids_to_delete,))
        
        new_balance = u_info['balance'] - total_p
        new_bought_today = u_info['bought_today'] + qty
        cur.execute("UPDATE users SET balance = %s, bought_today = %s WHERE user_id = %s", (new_balance, new_bought_today, user_id))

        now_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        items_str_db = "\n".join(items)
        cur.execute("INSERT INTO orders (user_id, product, items, total, time) VALUES (%s, %s, %s, %s, %s)",
                    (user_id, code.upper(), items_str_db, total_p, now_time))
        conn.commit()
        cur.close()
        conn.close()

        await query.message.delete()
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎉 **MUA THÀNH CÔNG!**\n\n🔑 **Tài khoản:**\n" + "\n".join([f"`{i}`" for i in items]) + f"\n\n🪙 Dư: {new_balance:,}đ\n\n👇 **MENU CHÍNH**",
            reply_markup=main_menu(), parse_mode="Markdown"
        )

    elif query.data == "orders":
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE user_id = %s ORDER BY id DESC LIMIT 5", (user_id,))
        user_orders = cur.fetchall()
        cur.close()
        conn.close()

        if not user_orders:
            text = "📦 **LỊCH SỬ ĐƠN HÀNG**\n\nBạn chưa có giao dịch mua hàng nào."
        else:
            text = "📦 **LỊCH SỬ ĐƠN HÀNG CỦA BẠN:**\n\n"
            for idx, ord in enumerate(user_orders, 1):
                items_formatted = ", ".join([f"`{i}`" for i in ord['items'].split("\n")])
                text += f"*{idx}. SP:* `{ord['product']}`\n🕒 *Thời gian:* {ord['time']}\n🔑 *Tài khoản:* {items_formatted}\n💰 *Tổng tiền:* `{ord['total']:,}đ`\n-----------------------------------\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Quay lại Menu", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif query.data == "deposit":
        keyboard = [
            [
                InlineKeyboardButton("40.000đ", callback_data="dep_40000"),
                InlineKeyboardButton("50.000đ", callback_data="dep_50000"),
                InlineKeyboardButton("60.000đ", callback_data="dep_60000")
            ],
            [
                InlineKeyboardButton("100.000đ", callback_data="dep_100000"),
                InlineKeyboardButton("200.000đ", callback_data="dep_200000"),
                InlineKeyboardButton("500.000đ", callback_data="dep_500000")
            ],
            [
                InlineKeyboardButton("1.000.000đ", callback_data="dep_1000000")
            ],
            [
                InlineKeyboardButton("🔙 Quay lại Menu", callback_data="back")
            ]
        ]
        await query.edit_message_text(
            "💳 **CHỌN SỐ TIỀN NẠP**\n\n👇 Chọn mệnh giá:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif query.data.startswith("dep_"):
        amt = int(query.data.split("_")[1])
        context.user_data['pending_amt'] = amt
        keyboard = [
            [InlineKeyboardButton("🔄 Đã chuyển khoản", callback_data="check_deposit")], 
            [InlineKeyboardButton("🔙 Quay lại", callback_data="deposit")]
        ]
        text = (
            f"💳 **THÔNG TIN CHUYỂN KHOẢN**\n\n"
            f"🏦 Ngân hàng: `VCB Bank`\n"
            f"👤 Chủ tài khoản: `TA NHU HAI`\n"
            f"🔢 Số tài khoản: `1071079951`\n"
            f"💵 Số tiền: `{amt:,}đ`\n"
            f"📝 Nội dung chuyển khoản: `NAP{user_id}`\n\n"
            f"⚠️ *Lưu ý: Chuyển đúng số tiền và đúng nội dung để được duyệt nhanh chóng.*"
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif query.data == "check_deposit":
        amt = context.user_data.get('pending_amt', 0)
        await query.edit_message_text("⏳ Đã gửi yêu cầu nạp tiền, chờ Admin duyệt.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu", callback_data="back")]]))
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🔔 Yêu cầu nạp {amt:,}đ từ ID `{user_id}`",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Duyệt", callback_data=f"confirm_pay_{user_id}_{amt}"),
                InlineKeyboardButton("❌ Huỷ", callback_data=f"cancel_pay_{user_id}")
            ]]), parse_mode="Markdown"
        )

    elif query.data.startswith("confirm_pay_"):
        if user_id != ADMIN_ID: return
        _, _, tid, amt = query.data.split("_")
        tid, amt = int(tid), int(amt)
        u = get_user(tid)
        
        new_balance = u["balance"] + amt
        new_deposit = u["total_deposit"] + amt
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET balance = %s, total_deposit = %s WHERE user_id = %s", (new_balance, new_deposit, tid))
        conn.commit()
        cur.close()
        conn.close()

        await query.edit_message_text(f"✅ Đã duyệt nạp {amt:,}đ cho `{tid}`", parse_mode="Markdown")
        try:
            await context.bot.send_message(chat_id=tid, text=f"🎉 **NẠP TIỀN THÀNH CÔNG!** +{amt:,}đ\n\n👇 **MENU CHÍNH**", reply_markup=main_menu(), parse_mode="Markdown")
        except: pass

    elif query.data == "back":
        await query.edit_message_text("🏠 **MENU CHÍNH**", reply_markup=main_menu(), parse_mode="Markdown")
    
    elif query.data == "invite_friends":
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
        text = (
            f"🎁 **MỜI BẠN BÈ NHẬN THƯỞNG**\n\n"
            f"🔗 Link giới thiệu của bạn:\n`{ref_link}`\n\n"
            f"👇 Hãy gửi link này cho bạn bè để mời họ tham gia!"
        )
        keyboard = [[InlineKeyboardButton("🔙 Quay lại Menu", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif query.data == "contact":
        keyboard = [[InlineKeyboardButton("🔙 Quay lại Menu", callback_data="back")]]
        await query.edit_message_text("💬 **LIÊN HỆ HỖ TRỢ**\n\nMọi thắc mắc vui lòng liên hệ Admin để được hỗ trợ trực tiếp.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ==============================
# KHỞI CHẠY BOT
# ==============================
app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("baotri", turn_on_maintenance))   
app.add_handler(CommandHandler("mo", turn_off_maintenance))       
app.add_handler(CommandHandler("thongbao", broadcast_message))
app.add_handler(CommandHandler("ThemtaikhoanCm88", add_cm88))
app.add_handler(CommandHandler("ThemtaikhoanSc88", add_sc88))
app.add_handler(CommandHandler("ThemtaikhoanC168", add_c168))
app.add_handler(CommandHandler("khohang", check_stock))
app.add_handler(CommandHandler("cong", add_money))
app.add_handler(CallbackQueryHandler(button))

print("🤖 BOT ĐÃ KẾT NỐI DATABASE TRÊN MÂY THÀNH CÔNG!")

await app.initialize()
await app.start()
