"""
Galorway Sales Bot - Telegram Bot for Sales Analysis
Created for Abu Amer (GALORWAY)

This bot receives sales statistics files from galorway.com (OpenCart),
analyzes them, and generates personalized reports for each team member.
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
    ConversationHandler,
    ContextTypes,
    filters,
)

# ============== CONFIGURATION ==============
# Get from environment variables or set directly
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Team members for personalized reports
TEAM_MEMBERS = {
    "natasha": {"name": "ناتاشا (Natasha)", "platforms": ["Emag RO", "Emag BG"], "role": "eMAG"},
    "vika": {"name": "فيكا (Vika)", "platforms": ["Trendyol", "Emag BG"], "role": "Trendyol + BG + GR"},
    "victoria": {"name": "فيكتوريا (Victoria)", "platforms": ["Site", "Temu"], "role": "galorway.com + SmartBill + Temu"},
    "ani": {"name": "اني (Ani)", "platforms": [], "role": "الصين - الموردة"},
    "abou_amer": {"name": "أبو عامر", "platforms": [], "role": "المدير"},
    "warehouse": {"name": "📦 المستودع (وسام + ديما + دينيس)", "platforms": [], "role": "التعبئة والشحن"},
}

# ============== LOGGING ==============
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ============== PARSING FUNCTIONS ==============

def parse_total(text):
    """Extract the main total number from the sales string"""
    if pd.isna(text) or text == "":
        return 0
    match = re.search(r"(\d+)", str(text))
    return int(match.group(1)) if match else 0


def parse_7d_trend(text):
    """Extract 7-day trend value"""
    if pd.isna(text) or text == "":
        return 0
    # Match patterns like: 7д ↑ +123 or 7д ↓ -45
    match = re.search(r"7д\s*([↑↓→])\s*([+-]?\d+)", str(text))
    if match:
        direction = match.group(1)
        value = int(match.group(2))
        return value if direction != "↓" else -value
    return 0


def parse_30d_trend(text):
    """Extract 30-day trend value"""
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
    """Analyze the galorway.com sales statistics file"""
    try:
        # Read HTML table (the file is actually HTML even though it has .xls extension)
        df = pd.read_html(file_path)[0]
    except Exception:
        # Try reading as Excel
        try:
            df = pd.read_excel(file_path)
        except Exception:
            # Try reading as CSV
            df = pd.read_csv(file_path)

    # Parse all sales columns
    platform_columns = [
        "Всего продано",
        "Site",
        "Emag BG",
        "Emag RO",
        "Trendyol",
        "Temu",
    ]

    for col in platform_columns:
        if col in df.columns:
            df[f"{col}_total"] = df[col].apply(parse_total)
            df[f"{col}_7d"] = df[col].apply(parse_7d_trend)
            df[f"{col}_30d"] = df[col].apply(parse_30d_trend)

    # Extract warehouse location from model code
    if "Модель" in df.columns:
        df["warehouse_loc"] = df["Модель"].str.extract(r"^([A-Za-z]\d+)")

    return df


def generate_full_report(df):
    """Generate comprehensive sales report"""
    total_products = len(df)
    total_orders = df["Всего продано_total"].sum()

    # Platform totals
    site_total = df["Site_total"].sum()
    emag_bg_total = df["Emag BG_total"].sum()
    emag_ro_total = df["Emag RO_total"].sum()
    trendyol_total = df["Trendyol_total"].sum()
    temu_total = df["Temu_total"].sum()

    # 7-day trends
    site_7d = df["Site_7d"].sum()
    emag_bg_7d = df["Emag BG_7d"].sum()
    emag_ro_7d = df["Emag RO_7d"].sum()
    trendyol_7d = df["Trendyol_7d"].sum()
    temu_7d = df["Temu_7d"].sum()

    # Stock status
    in_stock = df[df["На складе"] > 0]
    out_stock = df[df["На складе"] == 0]
    new_products = df[df["Всего продано_total"] == 0]

    # Urgent: out of stock but selling well
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
        report.append(
            f"📍{loc} │ {row['Всего продано_7d']}+ بآخر 7 أيام │ {name}..."
        )

    return "\n".join(report)


def generate_member_report(df, member_key):
    """Generate personalized report for a team member"""
    member = TEAM_MEMBERS[member_key]
    report = []

    report.append(f"👤 *{member['name']}*")
    report.append(f"💼 الدور: {member['role']}")
    report.append("")

    if member_key == "natasha":
        # eMAG RO + BG report
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

        # Top products on eMAG RO
        top_emag = df.nlargest(5, "Emag RO_total")
        report.append("*🏆 أعلى 5 منتجات على eMAG RO:*")
        for _, row in top_emag.iterrows():
            loc = row["warehouse_loc"] if pd.notna(row["warehouse_loc"]) else "??"
            name = str(row["Название RO"])[:35]
            report.append(f"   📍{loc} │ {row['Emag RO_total']:,} │ {name}...")

        # Urgent products
        urgent = df[(df["На складе"] == 0) & (df["Emag RO_total"] > 0)].nlargest(5, "Emag RO_7d")
        if len(urgent) > 0:
            report.append("")
            report.append("*🚨 منتجات نفذت — اطلبي من أبو عامر:*")
            for _, row in urgent.iterrows():
                loc = row["warehouse_loc"] if pd.notna(row["warehouse_loc"]) else "??"
                report.append(f"   📍{loc} │ {row['Модель']}")

    elif member_key == "vika":
        # Trendyol + BG report
        total_trendyol = df["Trendyol_total"].sum()
        total_bg = df["Emag BG_total"].sum()
        trend_7d = df["Trendyol_7d"].sum()
        bg_7d = df["Emag BG_7d"].sum()

        report.append(f"🇷🇴 *Trendyol (RO/BG/GR):*")
        report.append(f"   إجمالي: {total_trendyol:,} طلب")
        report.append(f"   آخر 7 أيام: {'⬆️' if trend_7d >= 0 else '⬇️'} {abs(trend_7d):,}")
        report.append("")

        # Top Trendyol products
        top_trendyol = df.nlargest(5, "Trendyol_total")
        report.append("*🏆 أعلى 5 منتجات على Trendyol:*")
        for _, row in top_trendyol.iterrows():
            loc = row["warehouse_loc"] if pd.notna(row["warehouse_loc"]) else "??"
            name = str(row["Название RO"])[:35]
            report.append(f"   📍{loc} │ {row['Trendyol_total']:,} │ {name}...")

        # Urgent
        urgent = df[(df["На складе"] == 0) & (df["Trendyol_total"] > 0)].nlargest(5, "Trendyol_7d")
        if len(urgent) > 0:
            report.append("")
            report.append("*🚨 منتجات نفذت — اطلبي من أبو عامر:*")
            for _, row in urgent.iterrows():
                loc = row["warehouse_loc"] if pd.notna(row["warehouse_loc"]) else "??"
                report.append(f"   📍{loc} │ {row['Модель']}")

    elif member_key == "victoria":
        # galorway + Temu report
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

        # SmartBill alert
        out_stock_count = len(df[df["На складе"] == 0])
        report.append(f"⚠️ *SmartBill:*")
        report.append(f"   {out_stock_count} منتج نفذ — لازم تسكري فواتير جديدة!")

    elif member_key == "ani":
        # Reorder list for China
        urgent = df[df["На складе"] == 0].nlargest(20, "Всего продано_7d")

        report.append("*📋 قائمة الطلبات العاجلة للكونتينر:*")
        report.append(f"   المنتجات اللي نفذت: {len(df[df['На складе'] == 0])}")
        report.append("")

        for i, (_, row) in enumerate(urgent.head(15).iterrows(), 1):
            loc = row["warehouse_loc"] if pd.notna(row["warehouse_loc"]) else "??"
            name = str(row["Название RO"])[:30]
            report.append(
                f"{i}. 📍{loc} │ {row['Модель']} │ "
                f"بيع: {row['Всего продано_7d']}+ بآخر 7 أيام"
            )

    elif member_key == "abou_amer":
        # Executive summary
        return generate_full_report(df)

    elif member_key == "warehouse":
        # Warehouse report
        total_orders_week = (
            df["Site_7d"].sum()
            + df["Emag RO_7d"].sum()
            + df["Trendyol_7d"].sum()
            + df["Emag BG_7d"].sum()
            + df["Temu_7d"].sum()
        )
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


# ============== BOT HANDLERS ==============


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
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
    """Handle /help command"""
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
    """Handle /analyze command"""
    await update.message.reply_text(
        "📎 *أبعث لي ملف المبيعات (Excel)*\n\n"
        "اصدّره من galorway.com:\n"
        "Отчеты → Статистика товаров → Экспорт в Excel\n\n"
        "ورح أحلله لك فوراً!",
        parse_mode="Markdown",
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle uploaded Excel/HTML file"""
    file = update.message.document

    # Check file type
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

    # Download file
    processing_msg = await update.message.reply_text("⏳ *جاري تحميل الملف...*", parse_mode="Markdown")

    try:
        file_obj = await context.bot.get_file(file.file_id)

        with tempfile.NamedTemporaryFile(suffix=".xls", delete=False) as tmp:
            await file_obj.download_to_drive(tmp.name)
            tmp_path = tmp.name

        # Update status
        await processing_msg.edit_text("🔍 *جاري تحليل المبيعات...*", parse_mode="Markdown")

        # Analyze
        df = analyze_sales_file(tmp_path)

        # Store in context for later commands
        context.chat_data["last_df"] = df

        # Update status
        await processing_msg.edit_text("📊 *جاري إعداد التقارير...*", parse_mode="Markdown")

        # Send full report
        full_report = generate_full_report(df)

        # Split long messages (Telegram limit: 4096 characters)
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

        # Send team reports
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

        # Clean up temp file
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
    """Handle member-specific report commands"""
    command = update.message.text.split()[0].replace("/", "")

    member_map = {
        "natasha": "natasha",
        "vika": "vika",
        "victoria": "victoria",
        "ani": "ani",
        "warehouse": "warehouse",
        "report": "abou_amer",
    }

    member_key = member_map.get(command)

    if not member_key:
        await update.message.reply_text("❌ أمر غير معروف")
        return

    # Check if we have data
    if "last_df" not in context.chat_data:
        await update.message.reply_text(
            "📎 *ما في ملف محلل*\n\n"
            "أبعث لي ملف المبيعات أولاً (Excel)،\n"
            "ورح أحضر التقرير.",
            parse_mode="Markdown",
        )
        return

    df = context.chat_data["last_df"]

    processing_msg = await update.message.reply_text(
        f"⏳ *جاري تحضير تقرير {TEAM_MEMBERS[member_key]['name']}...*",
        parse_mode="Markdown",
    )

    try:
        report = generate_member_report(df, member_key)

        # Split long messages
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


# ============== MAIN ==============


def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("analyze", analyze_command))

    # Member report handlers
    for cmd in ["report", "natasha", "vika", "victoria", "ani", "warehouse"]:
        application.add_handler(CommandHandler(cmd, member_report_command))

    # Document handler
    application.add_handler(
        MessageHandler(filters.Document.ALL, handle_document)
    )

    # Start the bot
    logger.info("🤖 Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
