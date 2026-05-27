"""
Galorway Sales Bot - Telegram Bot with Webhook for Render
Created for Abu Amer (GALORWAY)
"""

import os
import re
import logging
import tempfile
from datetime import datetime

import pandas as pd
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ============== CONFIGURATION ==============
BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://galorway-bot.onrender.com")
PORT = int(os.environ.get("PORT", 10000))

# ============== TEAM MEMBERS ==============
TEAM_MEMBERS = {
    "natasha": {"name": "ناتاشا (Natasha)", "role": "eMAG"},
    "vika": {"name": "فيكا (Vika)", "role": "Trendyol + BG + GR"},
    "victoria": {"name": "فيكتوريا (Victoria)", "role": "galorway.com + SmartBill + Temu"},
    "ani": {"name": "اني (Ani)", "role": "الصين - الموردة"},
    "abou_amer": {"name": "أبو عامر", "role": "المدير"},
    "warehouse": {"name": "المستودع (وسام + ديما + دينيس)", "role": "التعبئة والشحن"},
}

# Store data
last_df_store = {}

# ============== LOGGING ==============
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ============== PARSING ==============
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

# ============== ANALYSIS ==============
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

    if "Модель" in df.columns:
        df["warehouse_loc"] = df["Модель"].str.extract(r"^([A-Za-z]\d+)")
    return df

def generate_full_report(df):
    total_products = len(df)
    site_total = df["Site_total"].sum()
    emag_ro_total = df["Emag RO_total"].sum()
    trendyol_total = df["Trendyol_total"].sum()
    temu_total = df["Temu_total"].sum()
    emag_bg_total = df["Emag BG_total"].sum()

    site_7d = df["Site_7d"].sum()
    emag_ro_7d = df["Emag RO_7d"].sum()
    trendyol_7d = df["Trendyol_7d"].sum()
    temu_7d = df["Temu_7d"].sum()
    emag_bg_7d = df["Emag BG_7d"].sum()

    in_stock = df[df["На складе"] > 0]
    out_stock = df[df["На складе"] == 0]
    new_products = df[df["Всего продано_total"] == 0]
    urgent = df[df["На складе"] == 0].nlargest(10, "Всего продано_7d")

    report = []
    report.append("📊 *تقرير المبيعات — GALORWAY*")
    report.append(f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d')}")
    report.append(f"📦 عدد المنتجات: {total_products:,}")
    report.append("")
    report.append("*📈 أداء المنصات:*")
    report.append(f"🇷🇴 eMAG RO: {emag_ro_total:,} طلب")
    report.append(f"🇺🇦 galorway.com: {site_total:,} طلب")
    report.append(f"🇷🇴 Trendyol: {trendyol_total:,} طلب")
    report.append(f"🇧🇬 Emag BG: {emag_bg_total:,} طلب")
    report.append(f"📦 Temu: {temu_total:,} طلب")
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
    report.append("*🚨 منتجات نفذت وبتمبيع بكثرة:*")
    for _, row in urgent.iterrows():
        loc = row["warehouse_loc"] if pd.notna(row["warehouse_loc"]) else "??"
        name = str(row["Название RO"])[:35]
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
        ro_7d = df["Emag RO_7d"].sum()
        report.append(f"🇷🇴 *eMAG RO:* إجمالي {total_ro:,} │ 7 أيام {'⬆️' if ro_7d >= 0 else '⬇️'} {abs(ro_7d):,}")
        urgent = df[(df["На складе"] == 0) & (df["Emag RO_total"] > 0)].nlargest(5, "Emag RO_7d")
        if len(urgent) > 0:
            report.append("*🚨 نفذت — اطلبي من أبو عامر:*")
            for _, row in urgent.iterrows():
                loc = row["warehouse_loc"] if pd.notna(row["warehouse_loc"]) else "??"
                report.append(f"📍{loc} │ {row['Модель']}")

    elif member_key == "vika":
        total_trendyol = df["Trendyol_total"].sum()
        trend_7d = df["Trendyol_7d"].sum()
        report.append(f"🇷🇴 *Trendyol:* إجمالي {total_trendyol:,} │ 7 أيام {'⬆️' if trend_7d >= 0 else '⬇️'} {abs(trend_7d):,}")
        urgent = df[(df["На складе"] == 0) & (df["Trendyol_total"] > 0)].nlargest(5, "Trendyol_7d")
        if len(urgent) > 0:
            report.append("*🚨 نفذت — اطلبي من أبو عامر:*")
            for _, row in urgent.iterrows():
                loc = row["warehouse_loc"] if pd.notna(row["warehouse_loc"]) else "??"
                report.append(f"📍{loc} │ {row['Модель']}")

    elif member_key == "victoria":
        total_site = df["Site_total"].sum()
        total_temu = df["Temu_total"].sum()
        site_7d = df["Site_7d"].sum()
        temu_7d = df["Temu_7d"].sum()
        report.append(f"🇺🇦 *galorway.com:* إجمالي {total_site:,} │ 7 أيام {'⬆️' if site_7d >= 0 else '⬇️'} {abs(site_7d):,}")
        report.append(f"📦 *Temu:* إجمالي {total_temu:,} │ 7 أيام {'⬆️' if temu_7d >= 0 else '⬇️'} {abs(temu_7d):,}")
        out_stock_count = len(df[df["На складе"] == 0])
        report.append(f"⚠️ *SmartBill:* {out_stock_count} منتج نفذ — لازم تسكري فواتير!")

    elif member_key == "ani":
        urgent = df[df["На складе"] == 0].nlargest(15, "Всего продано_7d")
        report.append(f"*📋 قائمة الطلبات العاجلة ({len(df[df['На складе'] == 0])} منتج نفذ):*")
        report.append("")
        for i, (_, row) in enumerate(urgent.iterrows(), 1):
            loc = row["warehouse_loc"] if pd.notna(row["warehouse_loc"]) else "??"
            report.append(f"{i}. 📍{loc} │ {row['Модель']} │ بيع: {row['Всего продано_7d']}+ بآخر 7 أيام")

    elif member_key == "abou_amer":
        return generate_full_report(df)

    elif member_key == "warehouse":
        total_orders_week = df["Site_7d"].sum() + df["Emag RO_7d"].sum() + df["Trendyol_7d"].sum() + df["Emag BG_7d"].sum() + df["Temu_7d"].sum()
        report.append(f"*📦 المستودع — ملخص الأسبوع*")
        report.append(f"الطلبات الأسبوعية: ~{total_orders_week:,}")
        low_stock = df[(df["На складе"] > 0) & (df["На складе"] < 50)].nlargest(8, "Всего продано_7d")
        if len(low_stock) > 0:
            report.append("*⚠️ مخزون واطي (< 50):*")
            for _, row in low_stock.iterrows():
                loc = row["warehouse_loc"] if pd.notna(row["warehouse_loc"]) else "??"
                report.append(f"📍{loc} │ مخزون: {int(row['На складе'])} │ {row['Модель']}")

    return "\n".join(report)

# ============== HANDLERS ==============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "👋 *أهلاً أبو عامر!*\n\n"
        "أنا بوت GALORWAY — مساعدك الذكي لتحليل المبيعات.\n\n"
        "📋 *الأوامر:*\n"
        "/start — البداية\n"
        "/analyze — تحليل ملف مبيعات\n"
        "/report — التقرير العام\n"
        "/natasha — تقرير ناتاشا (eMAG)\n"
        "/vika — تقرير فيكا (Trendyol)\n"
        "/victoria — تقرير فيكتوريا\n"
        "/ani — طلبات الصين\n"
        "/warehouse — المستودع\n\n"
        "📎 *أو أبعث لي ملف المبيعات (Excel) مباشرة!*"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📎 أبعث لي ملف المبيعات أو استخدم الأوامر!", parse_mode="Markdown")

async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📎 *أبعث لي ملف المبيعات (Excel)*\n\n"
        "اصدّره من galorway.com:\n"
        "Отчеты → Статистика товаров → Экспорт в Excel",
        parse_mode="Markdown",
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.document
    valid_extensions = [".xls", ".xlsx", ".csv", ".html"]
    file_name = file.file_name.lower()

    if not any(file_name.endswith(ext) for ext in valid_extensions):
        await update.message.reply_text("❌ ملف غير مدعوم. أبعث .xls أو .xlsx", parse_mode="Markdown")
        return

    processing_msg = await update.message.reply_text("⏳ جاري التحميل...", parse_mode="Markdown")

    try:
        file_obj = await context.bot.get_file(file.file_id)
        with tempfile.NamedTemporaryFile(suffix=".xls", delete=False) as tmp:
            await file_obj.download_to_drive(tmp.name)
            tmp_path = tmp.name

        await processing_msg.edit_text("🔍 جاري التحليل...", parse_mode="Markdown")
        df = analyze_sales_file(tmp_path)
        chat_id = update.effective_chat.id
        last_df_store[chat_id] = df

        await processing_msg.edit_text("📊 جاري إعداد التقرير...", parse_mode="Markdown")
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
            "📋 *التقارير المخصصة:* /natasha /vika /victoria /ani /warehouse",
            parse_mode="Markdown",
        )
        os.unlink(tmp_path)
    except Exception as e:
        logger.error(f"Error: {e}")
        await processing_msg.edit_text(f"❌ خطأ: {str(e)[:200]}", parse_mode="Markdown")

async def member_report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command = update.message.text.split("/")[1] if "/" in update.message.text else ""
    member_map = {
        "report": "abou_amer", "natasha": "natasha", "vika": "vika",
        "victoria": "victoria", "ani": "ani", "warehouse": "warehouse",
    }
    member_key = member_map.get(command)

    if not member_key:
        await update.message.reply_text("❌ أمر غير معروف")
        return

    chat_id = update.effective_chat.id
    if chat_id not in last_df_store:
        await update.message.reply_text("📎 أبعث ملف المبيعات أولاً!", parse_mode="Markdown")
        return

    df = last_df_store[chat_id]
    processing_msg = await update.message.reply_text(f"⏳ جاري تحضير تقرير {TEAM_MEMBERS[member_key]['name']}...", parse_mode="Markdown")

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
        logger.error(f"Error: {e}")
        await processing_msg.edit_text(f"❌ خطأ: {str(e)[:200]}", parse_mode="Markdown")

# ============== MAIN ==============
def main():
    logger.info("🤖 Starting bot...")
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("analyze", analyze_command))
    
    for cmd in ["report", "natasha", "vika", "victoria", "ani", "warehouse"]:
        app.add_handler(CommandHandler(cmd, member_report_command))
    
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    logger.info(f"🌐 Webhook: {WEBHOOK_URL}")
    app.run_webhook(listen="0.0.0.0", port=PORT, webhook_url=WEBHOOK_URL)

if __name__ == "__main__":
    main()
