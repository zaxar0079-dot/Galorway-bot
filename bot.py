"""
Galorway Sales Bot - Telegram Bot with Webhook for Render
Created for Abu Amer (GALORWAY)
"""

import os
import re
import logging
import tempfile
import asyncio
from datetime import datetime
from flask import Flask, request

import pandas as pd
import telegram
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ============== CONFIGURATION ==============
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8820342043:AAGyhpnkQcQA0pqXlQD5guKtZlBjykyE04M")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://galorway-bot.onrender.com")

# Flask app for webhook
flask_app = Flask(__name__)

# ============== TEAM MEMBERS ==============
TEAM_MEMBERS = {
    "natasha": {"name": "ناتاشا (Natasha)", "platforms": ["Emag RO", "Emag BG"], "role": "eMAG"},
    "vika": {"name": "فيكا (Vika)", "platforms": ["Trendyol", "Emag BG"], "role": "Trendyol + BG + GR"},
    "victoria": {"name": "فيكتوريا (Victoria)", "platforms": ["Site", "Temu"], "role": "galorway.com + SmartBill + Temu"},
    "ani": {"name": "اني (Ani)", "platforms": [], "role": "الصين - الموردة"},
    "abou_amer": {"name": "أبو عامر", "platforms": [], "role": "المدير"},
    "warehouse": {"name": "📦 المستودع (وسام + ديما + دينيس)", "platforms": [], "role": "التعبئة والشحن"},
}

# Store last dataframe
last_df_store = {}

# ============== LOGGING ==============
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ============== PARSING FUNCTIONS ==============
def parse_total(text):
    if pd.isna(text) or text == "":
        return 0
    match = re.search(r"(\d+)", str(text))
    return int(match.group(1)) if match else 0

def parse_7d_trend(text):
    if pd.isna(text) or text == "":
        return 0
    match = re.search(r"7д\s*([↑↓→])\s*([+-]?\d+)", str(text))
    if match:
        direction = match.group(1)
        value = int(match.group(2))
        return value if direction != "↓" else -value
    return 0

def parse_30d_trend(text):
    if pd.isna(text) or text == "":
        return 0
    match = re.search(r"30д\s*([↑↓→])\s*([+-]?\d+)", str(text))
    if match:
        direction = match.group(1)
        value = int(match.group(2))
        return value if direction != "↓" else -value
    return 0

# ============== ANALYSIS FUNCTIONS ==============
def analyze_sales_file(file_path):
    try:
        df = pd.read_html(file_path)[0]
    except Exception:
        try:
            df = pd.read_excel(file_path)
        except Exception:
            df = pd.read_csv(file_path)

    platform_columns = ["Всего продано", "Site", "Emag BG", "Emag RO", "Trendyol", "Temu"]
    for col in platform_columns:
        if col in df.columns:
            df[f"{col}_total"] = df[col].apply(parse_total)
            df[f"{col}_7d"] = df[col].apply(parse_7d_trend)
            df[f"{col}_30d"] = df[col].apply(parse_30d_trend)

    if "Модель" in df.columns:
        df["warehouse_loc"] = df["Модель"].str.extract(r"^([A-Za-z]\d+)")
    return df

def generate_full_report(df):
    total_products = len(df)
    total_orders = df["Всего продано_total"].sum()

    site_total = df["Site_total"].sum()
    emag_bg_total = df["Emag BG_total"].sum()
    emag_ro_total = df["Emag RO_total"].sum()
    trendyol_total = df["Trendyol_total"].sum()
    temu_total = df["Temu_total"].sum()

    site_7d = df["Site_7d"].sum()
    emag_bg_7d = df["Emag BG_7d"].sum()
    emag_ro_7d = df["Emag RO_7d"].sum()
    trendyol_7d = df["Trendyol_7d"].sum()
    temu_7d = df["Temu_7d"].sum()

    in_stock = df[df["На складе"] > 0]
    out_stock = df[df["На складе"] == 0]
    new_products = df[df["Всего продано_total"] == 0]
    urgent = df[df["На складе"] == 0].nlargest(15, "Всего продано_7d")

    report = []
    report.append("📊 *تقرير المبيعات — GALORWAY*")
    report.append(f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d')}")
    report.append(f"📦 عدد المنتجات: {total_products:,}")
    report.append("")
    report.append("*📈 أداء المنصات:*")
    report.append(f"🇷🇴 eMAG RO: {emag_ro_total:,} طلب (56%)")
    report.append(f"🇺🇦 galorway.com: {site_total:,} طلب (29%)")
    report.append(f"🇷🇴 Trendyol: {trendyol_total:,} طلب (13%)")
    report.append(f"🇧🇬 Emag BG: {emag_bg_total:,} طلب (1%)")
    report.append(f"📦 Temu: {temu_total:,} طلب (1%)")
    report.append("")
    report.append("*📈 آخر 7 أيام:*")
    report.append(f"🇷🇴 eMAG RO: {'⬆️' if emag_ro_7d >= 0 else '⬇️'} {abs(emag_ro_7d):,}")
    report.append(f"🇺🇦 galorway: {'⬆️' if site_7d >= 0 else '⬇️'} {abs(site_7d):,}")
    report.append(f"🇷🇴 Trendyol: {'⬆️' if trendyol_7d >= 0 else '⬇️'} {abs(trendyol_7d):,}")
    report.append(f"🇧🇬 Emag BG: {'⬆️' if emag_bg_7d >= 0 else '⬇️'} {abs(emag_bg_7d):,}")
    report.append(f"📦 Temu: {'⬆️' if temu_7d >= 0 else '⬇️'} {abs(temu_7d):,}")
    report.append("")
    report.append("*⚠️ حالة المخزون:*")
    report.append(f"✅ بمخزون: {len(in_stock)} ({len(in_stock)/total_products*100:.0f}%)")
    report.append(f"🔴 نفذ: {len(out_stock)} ({len(out_stock)/total_products*100:.0f}%)")
    report.append(f"🆕 منتجات جديدة: {len(new_products)} ({len(new_products)/total_products*100:.0f}%)")
    report.append("")
    report.append("*🚨 منتجات نفذت وبتمبيع بكثرة (أولوية طلب):*")
    for _, row in urgent.head(10).iterrows():
        loc = row["warehouse_loc"] if pd.notna(row["warehouse_loc"]) else "??"
        name = str(row["Название RO"])[:40]
        report.append(f"📍{loc} │ {row['Всего продано_7d']}+ بآخر 7 أيام │ {name}...")
    return "\n".join(report)

def generate_member_report(df, member_key):
    member = TEAM_MEMBERS[member_key]
    report = []
    report.append(f"👤 *{member['name']}*")
    report.append(f"💼 الدور: {member['role']}")
    report.append("")

    if member_key == "natasha":
        total_ro = df["Emag RO_total"].sum()
        total_bg = df["Emag BG_total"].sum()
        ro_7d = df["Emag RO_7d"].sum()
        bg_7d = df["Emag BG_7d"].sum()
        report.append(f"🇷🇴 *eMAG RO:*")
        report.append(f"   إجمالي: {total_ro:,} طلب")
        report.append(f"   آخر 7 أيام: {'⬆️' if ro_7d >= 0 else '⬇️'} {abs(ro_7d):,}")
        report.append("")
        report.append(f"🇧🇬 *Emag BG:*")
        report.append(f"   إجمالي: {total_bg:,} طلب")
        report.append(f"   آخر 7 أيام: {'⬆️' if bg_7d >= 0 else '⬇️'} {abs(bg_7d):,}")
        report.append("")
        top_emag = df.nlargest(5, "Emag RO_total")
        report.append("*🏆 أعلى 5 منتجات على eMAG RO:*")
        for _, row in top_emag.iterrows():
            loc = row["warehouse_loc"] if pd.notna(row["warehouse_loc"]) else "??"
            name = str(row["Название RO"])[:35]
            report.append(f"   📍{loc} │ {row['Emag RO_total']:,} │ {name}...")
        urgent = df[(df["На складе"] == 0) & (df["Emag RO_total"] > 0)].nlargest(5, "Emag RO_7d")
        if len(urgent) > 0:
            report.append("")
            report.append("*🚨 منتجات نفذت — اطلبي من أبو عامر:*")
            for _, row in urgent.iterrows():
                loc = row["warehouse_loc"] if pd.notna(row["warehouse_loc"]) else "??"
                report.append(f"   📍{loc} │ {row['Модель']}")

    elif member_key == "vika":
        total_trendyol = df["Trendyol_total"].sum()
        total_bg = df["Emag BG_total"].sum()
        trend_7d = df["Trendyol_7d"].sum()
        bg_7d = df["Emag BG_7d"].sum()
        report.append(f"🇷🇴 *Trendyol (RO/BG/GR):*")
        report.append(f"   إجمالي: {total_trendyol:,} طلب")
        report.append(f"   آخر 7 أيام: {'⬆️' if trend_7d >= 0 else '⬇️'} {abs(trendyol_7d):,}")
        report.append("")
        top_trendyol = df.nlargest(5, "Trendyol_total")
        report.append("*🏆 أعلى 5 منتجات على Trendyol:*")
        for _, row in top_trendyol.iterrows():
            loc = row["warehouse_loc"] if pd.notna(row["warehouse_loc"]) else "??"
            name = str(row["Название RO"])[:35]
            report.append(f"   📍{loc} │ {row['Trendyol_total']:,} │ {name}...")
        urgent = df[(df["На складе"] == 0) & (df["Trendyol_total"] > 0)].nlargest(5, "Trendyol_7d")
        if len(urgent) > 0:
            report.append("")
            report.append("*🚨 منتجات نفذت — اطلبي من أبو عامر:*")
            for _, row in urgent.iterrows():
                loc = row["warehouse_loc"] if pd.notna(row["warehouse_loc"]) else "??"
                report.append(f"   📍{loc} │ {row['Модель']}")

    elif member_key == "victoria":
        total_site = df["Site_total"].sum()
        total_temu = df["Temu_total"].sum()
        site_7d = df["Site_7d"].sum()
        temu_7d = df["Temu_7d"].sum()
        report.append(f"🇺🇦 *galorway.com:*")
        report.append(f"   إجمالي: {total_site:,} طلب")
        report.append(f"   آخر 7 أيام: {'⬆️' if site_7d >= 0 else '⬇️'} {abs(site_7d):,}")
        report.append("")
        report.append(f"📦 *Temu:*")
        report.append(f"   إجمالي: {total_temu:,} طلب")
        report.append(f"   آخر 7 أيام: {'⬆️' if temu_7d >= 0 else '⬇️'} {abs(temu_7d):,}")
        report.append("")
        out_stock_count = len(df[df["На складе"] == 0])
        report.append(f"⚠️ *SmartBill:*")
        report.append(f"   {out_stock_count} منتج نفذ — لازم تسكري فواتير جديدة!")

    elif member_key == "ani":
        urgent = df[df["На складе"] == 0].nlargest(20, "Всего продано_7d")
        report.append("*📋 قائمة الطلبات العاجلة للكونتينر:*")
        report.append(f"   المنتجات اللي نفذت: {len(df[df['На складе'] == 0])}")
        report.append("")
        for i, (_, row) in enumerate(urgent.head(15).iterrows(), 1):
            loc = row["warehouse_loc"] if pd.notna(row["warehouse_loc"]) else "??"
            report.append(f"{i}. 📍{loc} │ {row['Модель']} │ بيع: {row['Всего продано_7d']}+ بآخر 7 أيام")

    elif member_key == "abou_amer":
        return generate_full_report(df)

    elif member_key == "warehouse":
        total_orders_week = df["Site_7d"].sum() + df["Emag RO_7d"].sum() + df["Trendyol_7d"].sum() + df["Emag BG_7d"].sum() + df["Temu_7d"].sum()
        products_to_pick = len(df[df["На складе"] > 0])
        report.append(f"*📦 المستودع — ملخص الأسبوع*")
        report.append(f"   الطلبات الأسبوعية: ~{total_orders_week:,}")
        report.append(f"   المنتجات بالمخزون: {products_to_pick}")
        report.append("")
        report.append("*⚠️ منتجات مخزونها واطي (أقل من 50):*")
        low_stock = df[(df["На складе"] > 0) & (df["На складе"] < 50)].nlargest(10, "Всего продано_7d")
        for _, row in low_stock.iterrows():
            loc = row["warehouse_loc"] if pd.notna(row["warehouse_loc"]) else "??"
            report.append(f"   📍{loc} │ المخزون: {int(row['На складе'])} │ {row['Модель']}")

    return "\n".join(report)

# ============== ASYNC HELPERS ==============
def run_async(coro):
    """Run async function in sync context"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

# ============== BOT HANDLERS ==============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "👋 *أهلاً أبو عامر!*\n\n"
        "أنا بوت GALORWAY — مساعدك الذكي لتحليل المبيعات.\n\n"
        "📋 *الأوامر المتاحة:*\n"
        "/analyze — تحليل ملف المبيعات\n"
        "/report — التقرير العام\n"
        "/natasha — تقرير ناتاشا (eMAG)\n"
        "/vika — تقرير فيكا (Trendyol)\n"
        "/victoria — تقرير فيكتوريا (galorway+Temu)\n"
        "/ani — قائمة الطلبات لاني (الصين)\n"
        "/warehouse — تقرير المستودع\n\n"
        "📎 *أو ببساطة:*\n"
        "أبعث لي ملف المبيعات (Excel) ورح أحلله لك!\n\n"
        "© GALORWAY 2025"
    )
    await update.message.reply_text(welcome_message, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📋 *كيفية الاستخدام:*\n\n"
        "1️⃣ صدّر ملف المبيعات من galorway.com\n"
        "   (Отчеты → Статистика товаров → Экспорт в Excel)\n\n"
        "2️⃣ أبعث الملف لهون\n\n"
        "3️⃣ البوت رح يحلله ويعطيك تقارير لكل شخص\n\n"
        "⚡ *أو استخدم الأوامر:*\n"
        "/report — التقرير العام\n"
        "/natasha — تقرير ناتاشا\n"
        "/vika — تقرير فيكا\n"
        "/victoria — تقرير فيكتوريا\n"
        "/ani — طلبات الصين\n"
        "/warehouse — المستودع"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📎 *أبعث لي ملف المبيعات (Excel)*\n\n"
        "اصدّره من galorway.com:\n"
        "Отчеты → Статистика товаров → Экспорт в Excel\n\n"
        "ورح أحلله لك فوراً!",
        parse_mode="Markdown",
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.document
    valid_extensions = [".xls", ".xlsx", ".csv", ".html"]
    file_name = file.file_name.lower()

    if not any(file_name.endswith(ext) for ext in valid_extensions):
        await update.message.reply_text(
            "❌ *ملف غير مدعوم*\n\n"
            "الملفات المدعومة:\n"
            "• .xls (ملف galorway.com)\n"
            "• .xlsx\n"
            "• .csv\n\n"
            "اصدّر الملف من galorway.com مباشرة.",
            parse_mode="Markdown",
        )
        return

    processing_msg = await update.message.reply_text("⏳ *جاري تحميل الملف...*", parse_mode="Markdown")

    try:
        file_obj = await context.bot.get_file(file.file_id)
        with tempfile.NamedTemporaryFile(suffix=".xls", delete=False) as tmp:
            await file_obj.download_to_drive(tmp.name)
            tmp_path = tmp.name

        await processing_msg.edit_text("🔍 *جاري تحليل المبيعات...*", parse_mode="Markdown")
        df = analyze_sales_file(tmp_path)
        
        # Store in global dict (keyed by chat_id)
        chat_id = update.effective_chat.id
        last_df_store[chat_id] = df

        await processing_msg.edit_text("📊 *جاري إعداد التقارير...*", parse_mode="Markdown")
        full_report = generate_full_report(df)

        if len(full_report) > 4000:
            parts = []
            current = ""
            for line in full_report.split("\n"):
                if len(current) + len(line) + 1 > 4000:
                    parts.append(current)
                    current = line + "\n"
                else:
                    current += line + "\n"
            if current:
                parts.append(current)
            await processing_msg.edit_text(parts[0], parse_mode="Markdown")
            for part in parts[1:]:
                await update.message.reply_text(part, parse_mode="Markdown")
        else:
            await processing_msg.edit_text(full_report, parse_mode="Markdown")

        await update.message.reply_text(
            "📋 *التقارير المخصصة:*\n\n"
            "استخدم الأوامر التالية لكل شخص:\n"
            "/natasha — ناتاشا (eMAG)\n"
            "/vika — فيكا (Trendyol)\n"
            "/victoria — فيكتوريا (galorway+Temu)\n"
            "/ani — أني (الصين)\n"
            "/warehouse — المستودع",
            parse_mode="Markdown",
        )
        os.unlink(tmp_path)

    except Exception as e:
        logger.error(f"Error processing file: {e}")
        await processing_msg.edit_text(
            f"❌ *خطأ بتحليل الملف*\n\n"
            f"السبب: {str(e)[:200]}\n\n"
            f"تأكد إن الملف صدّرته من galorway.com مباشرة.",
            parse_mode="Markdown",
        )

async def member_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command = update.message.text.split()[0].replace("/", "")
    member_map = {
        "report": "abou_amer",
        "natasha": "natasha",
        "vika": "vika",
        "victoria": "victoria",
        "ani": "ani",
        "warehouse": "warehouse",
    }
    member_key = member_map.get(command)

    if not member_key:
        await update.message.reply_text("❌ أمر غير معروف")
        return

    chat_id = update.effective_chat.id
    if chat_id not in last_df_store:
        await update.message.reply_text(
            "📎 *ما في ملف محلل*\n\n"
            "أبعث لي ملف المبيعات أولاً (Excel)،\n"
            "ورح أحضر التقرير.",
            parse_mode="Markdown",
        )
        return

    df = last_df_store[chat_id]
    processing_msg = await update.message.reply_text(
        f"⏳ *جاري تحضير تقرير {TEAM_MEMBERS[member_key]['name']}...*",
        parse_mode="Markdown",
    )

    try:
        report = generate_member_report(df, member_key)
        if len(report) > 4000:
            parts = []
            current = ""
            for line in report.split("\n"):
                if len(current) + len(line) + 1 > 4000:
                    parts.append(current)
                    current = line + "\n"
                else:
                    current += line + "\n"
            if current:
                parts.append(current)
            await processing_msg.edit_text(parts[0], parse_mode="Markdown")
            for part in parts[1:]:
                await update.message.reply_text(part, parse_mode="Markdown")
        else:
            await processing_msg.edit_text(report, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error generating report: {e}")
        await processing_msg.edit_text(
            f"❌ *خطأ بتحضير التقرير*\n{str(e)[:200]}",
            parse_mode="Markdown",
        )

# ============== SETUP BOT APPLICATION ==============
# Create the bot application once
bot_app = (
    Application.builder()
    .token(BOT_TOKEN)
    .updater(None)  # No polling, we use webhook
    .build()
)

# Add handlers
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("help", help_command))
bot_app.add_handler(CommandHandler("analyze", analyze_command))

for cmd in ["report", "natasha", "vika", "victoria", "ani", "warehouse"]:
    bot_app.add_handler(CommandHandler(cmd, member_report_command))

bot_app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

logger.info("🤖 Bot application initialized")

# ============== FLASK ROUTES ==============
@flask_app.route("/", methods=["POST"])
def webhook():
    """Receive webhook updates from Telegram"""
    if request.method == "POST":
        try:
            json_data = request.get_json(force=True)
            update = Update.de_json(json_data, bot_app.bot)
            
            # Process update using asyncio
            import asyncio
            asyncio.run(bot_app.process_update(update))
            return "OK", 200
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return "Error", 500
    return "Hello from Galorway Bot!", 200

@flask_app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return "OK", 200

# ============== MAIN ==============
if __name__ == "__main__":
    logger.info("🤖 Bot starting with webhook mode...")
    
    # Set webhook
    try:
        bot = telegram.Bot(BOT_TOKEN)
        bot.set_webhook(url=f"{WEBHOOK_URL}/")
        logger.info(f"✅ Webhook set to {WEBHOOK_URL}/")
    except Exception as e:
        logger.error(f"❌ Failed to set webhook: {e}")
    
    # Start Flask server
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)
