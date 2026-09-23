#!/usr/bin/env python3
"""
ربات مدیریت حقوق کارمندان
- کارمند نام خودش را انتخاب می‌کند → مدیر تأیید می‌کند
- کارمند عکس یا متن می‌فرستد → مدیر مبلغ را تعیین می‌کند → کارمند تأیید می‌کند
- دکمه‌های پایین صفحه برای کارمند
- تمام متن‌ها به فارسی
"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

import database as db

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing. Create a .env file (see .env.example)")

ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}
if not ADMIN_IDS:
    raise RuntimeError("ADMIN_IDS is missing or empty. Add your Telegram user ID(s).")

WAITING_AMOUNT = 1
WAITING_NAME = 2

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def employee_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("💰 موجودی"), KeyboardButton("📜 تاریخچه")],
        [KeyboardButton("ℹ️ راهنما")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def confirmation_keyboard(conf_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ تأیید", callback_data=f"conf_accept:{conf_id}"),
                InlineKeyboardButton("❌ رد", callback_data=f"conf_decline:{conf_id}"),
            ]
        ]
    )


def registration_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ قبول", callback_data=f"reg_accept:{telegram_id}"),
                InlineKeyboardButton("❌ رد", callback_data=f"reg_reject:{telegram_id}"),
            ]
        ]
    )


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str, **kwargs):
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text, **kwargs)
        except Exception as e:
            logger.warning("Could not notify admin %s: %s", admin_id, e)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    user = update.effective_user
    emp = db.get_employee_by_id(user.id)

    if emp:
        await update.message.reply_text(
            f"👋 سلام *{emp['name']}*!\n\n"
            f"موجودی فعلی شما: *{emp['balance']:.2f}*\n\n"
            "عکس یا متن کار خود را بفرستید.\n"
            "از دکمه‌های پایین صفحه هم می‌توانید استفاده کنید.",
            parse_mode="Markdown",
            reply_markup=employee_keyboard(),
        )
        return ConversationHandler.END

    pending = db.get_pending_registration(user.id)
    if pending:
        await update.message.reply_text(
            f"⏳ شما قبلاً نام *{pending['requested_name']}* را درخواست کرده‌اید.\n"
            "لطفاً منتظر تأیید مدیر بمانید.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"👋 سلام {user.first_name}!\n\n"
        "شما هنوز ثبت‌نام نشده‌اید.\n"
        "لطفاً **نام** مورد نظر خود را بفرستید (مثلاً: علی رضایی).\n\n"
        "برای انصراف /cancel را بزنید.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return WAITING_NAME


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    name = update.message.text.strip()

    if len(name) < 2:
        await update.message.reply_text("نام خیلی کوتاه است. لطفاً نام کامل بفرستید.")
        return WAITING_NAME

    if len(name) > 40:
        await update.message.reply_text("نام خیلی بلند است (حداکثر ۴۰ حرف).")
        return WAITING_NAME

    if db.get_employee_by_id(user.id):
        await update.message.reply_text("شما قبلاً ثبت‌نام شده‌اید!", reply_markup=employee_keyboard())
        return ConversationHandler.END

    ok = db.create_pending_registration(user.id, name)
    if not ok:
        await update.message.reply_text(
            f"نام *{name}* قبلاً استفاده شده یا خطایی رخ داد.\n"
            "لطفاً نام دیگری انتخاب کنید.",
            parse_mode="Markdown",
        )
        return WAITING_NAME

    await update.message.reply_text(
        f"✅ نام *{name}* ثبت شد.\n"
        "منتظر تأیید مدیر بمانید...",
        parse_mode="Markdown",
    )

    await notify_admins(
        context,
        f"🆕 درخواست ثبت‌نام جدید\n\n"
        f"نام: *{name}*\n"
        f"آیدی تلگرام: `{user.id}`\n"
        f"یوزرنیم: @{user.username or 'ندارد'}\n\n"
        "قبول یا رد کنید؟",
        parse_mode="Markdown",
        reply_markup=registration_keyboard(user.id),
    )

    return ConversationHandler.END


async def cancel_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("لغو شد. برای ثبت‌نام دوباره /start را بزنید.")
    return ConversationHandler.END


async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    emp = db.get_employee_by_id(user.id)
    if not emp:
        await update.message.reply_text("شما هنوز ثبت‌نام نشده‌اید. /start را بزنید.")
        return

    await update.message.reply_text(
        f"💰 *{emp['name']}*\n"
        f"موجودی فعلی: *{emp['balance']:.2f}*",
        parse_mode="Markdown",
        reply_markup=employee_keyboard(),
    )


async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    emp = db.get_employee_by_id(user.id)
    if not emp:
        await update.message.reply_text("شما هنوز ثبت‌نام نشده‌اید.")
        return

    txs = db.get_transactions(user.id, limit=15)
    if not txs:
        await update.message.reply_text("هنوز تراکنشی ندارید.", reply_markup=employee_keyboard())
        return

    type_fa = {"wage": "حقوق", "bonus": "پاداش", "fine": "جریمه", "pay": "پرداخت"}
    lines = [f"📜 آخرین تراکنش‌های *{emp['name']}*:"]
    for t in txs:
        sign = "+" if t["amount"] > 0 else ""
        note = f" – {t['note']}" if t["note"] else ""
        tname = type_fa.get(t["type"], t["type"])
        lines.append(f"• {tname}: {sign}{t['amount']:.2f}{note}")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=employee_keyboard(),
    )


async def handle_work_proof(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = (update.message.text or "").strip()

    if text == "💰 موجودی":
        await balance_cmd(update, context)
        return
    if text == "📜 تاریخچه":
        await history_cmd(update, context)
        return
    if text == "ℹ️ راهنما":
        await help_cmd(update, context)
        return

    emp = db.get_employee_by_id(user.id)

    if not emp:
        pending = db.get_pending_registration(user.id)
        if pending:
            await update.message.reply_text("⏳ ثبت‌نام شما هنوز در انتظار تأیید مدیر است.")
        else:
            await update.message.reply_text("شما ثبت‌نام نشده‌اید. /start را بزنید.")
        return

    if update.message.text and update.message.text.startswith("/"):
        return

    content_type = "photo" if update.message.photo else "text"
    text_content = update.message.caption or update.message.text
    photo_file_id = update.message.photo[-1].file_id if update.message.photo else None

    submission_id = db.create_submission(
        telegram_id=user.id,
        content_type=content_type,
        text_content=text_content,
        photo_file_id=photo_file_id,
    )

    await update.message.reply_text(
        f"✅ گزارش کار دریافت شد (شماره #{submission_id}).\nمنتظر تأیید مدیر بمانید.",
        reply_markup=employee_keyboard(),
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ تأیید", callback_data=f"approve:{submission_id}"),
                InlineKeyboardButton("❌ رد", callback_data=f"reject:{submission_id}"),
            ]
        ]
    )

    caption = (
        f"📥 گزارش کار جدید از *{emp['name']}*\n"
        f"شماره: #{submission_id}\n"
    )
    if text_content:
        caption += f"\nپیام:\n{text_content}"

    for admin_id in ADMIN_IDS:
        try:
            if content_type == "photo":
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=photo_file_id,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
            else:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=caption,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
        except Exception as e:
            logger.warning("Failed to notify admin %s: %s", admin_id, e)


async def registration_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.message.reply_text("فقط مدیر می‌تواند این کار را انجام دهد.")
        return

    data = query.data
    telegram_id = int(data.split(":")[1])
    pending = db.get_pending_registration(telegram_id)

    if not pending:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("این درخواست دیگر در انتظار نیست.")
        return

    name = pending["requested_name"]

    if data.startswith("reg_accept:"):
        if db.get_employee_by_name(name):
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(f"نام *{name}* قبلاً گرفته شده.", parse_mode="Markdown")
            db.delete_pending_registration(telegram_id)
            return

        ok = db.add_employee(telegram_id, name)
        db.delete_pending_registration(telegram_id)

        if not ok:
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text("ثبت‌نام ناموفق بود.")
            return

        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"✅ قبول شد! *{name}* ثبت‌نام شد.",
            parse_mode="Markdown",
        )

        try:
            await context.bot.send_message(
                chat_id=telegram_id,
                text=(
                    f"🎉 ثبت‌نام شما تأیید شد!\n\n"
                    f"شما با نام *{name}* ثبت شدید.\n"
                    "حالا می‌توانید عکس یا متن کار خود را بفرستید."
                ),
                parse_mode="Markdown",
                reply_markup=employee_keyboard(),
            )
        except Exception:
            pass

    elif data.startswith("reg_reject:"):
        db.delete_pending_registration(telegram_id)

        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"❌ درخواست *{name}* رد شد.",
            parse_mode="Markdown",
        )

        try:
            await context.bot.send_message(
                chat_id=telegram_id,
                text=(
                    f"❌ درخواست ثبت‌نام شما با نام *{name}* رد شد.\n"
                    "می‌توانید دوباره /start بزنید و نام دیگری انتخاب کنید."
                ),
                parse_mode="Markdown",
            )
        except Exception:
            pass


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("فقط مدیر می‌تواند این کار را انجام دهد.")
        return ConversationHandler.END

    data = query.data

    if data.startswith("approve:"):
        submission_id = int(data.split(":")[1])
        sub = db.get_submission(submission_id)
        if not sub or sub["status"] != "pending":
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text("این گزارش دیگر در انتظار نیست.")
            return ConversationHandler.END

        context.user_data["pending_submission_id"] = submission_id

        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"مبلغ حقوق برای گزارش #{submission_id} را وارد کنید:\n"
            "(یا /cancel برای انصراف)"
        )
        return WAITING_AMOUNT

    elif data.startswith("reject:"):
        submission_id = int(data.split(":")[1])
        sub = db.get_submission(submission_id)
        if not sub or sub["status"] != "pending":
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text("این گزارش دیگر در انتظار نیست.")
            return ConversationHandler.END

        db.reject_submission(submission_id)

        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"❌ گزارش #{submission_id} رد شد.")

        try:
            await context.bot.send_message(
                chat_id=sub["telegram_id"],
                text=f"❌ گزارش کار شما (#{submission_id}) توسط مدیر رد شد.",
                reply_markup=employee_keyboard(),
            )
        except Exception:
            pass

        return ConversationHandler.END

    return ConversationHandler.END


async def receive_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    text = update.message.text.strip().replace(",", ".")
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("لطفاً یک عدد مثبت وارد کنید (مثلاً 50 یا 75.5).")
        return WAITING_AMOUNT

    submission_id = context.user_data.get("pending_submission_id")
    if not submission_id:
        await update.message.reply_text("گزارشی در انتظار نیست.")
        return ConversationHandler.END

    sub = db.get_submission(submission_id)
    if not sub or sub["status"] != "pending":
        await update.message.reply_text("این گزارش دیگر در انتظار نیست.")
        return ConversationHandler.END

    emp = db.get_employee_by_id(sub["telegram_id"])
    name = emp["name"] if emp else "کارمند"

    conf_id = db.create_confirmation(
        telegram_id=sub["telegram_id"],
        amount=amount,
        type_="wage",
        note=f"حقوق بابت گزارش #{submission_id}",
        submission_id=submission_id,
    )

    db.approve_submission(submission_id, amount)

    await update.message.reply_text(
        f"⏳ مبلغ *{amount:.2f}* برای *{name}* پیشنهاد شد.\n"
        f"منتظر تأیید کارمند (شماره #{conf_id}).",
        parse_mode="Markdown",
    )

    try:
        await context.bot.send_message(
            chat_id=sub["telegram_id"],
            text=(
                f"📩 مدیر برای گزارش کار شما (#{submission_id}) مبلغ زیر را پیشنهاد داده:\n\n"
                f"مبلغ: *{amount:.2f}*\n\n"
                "لطفاً تأیید یا رد کنید:"
            ),
            parse_mode="Markdown",
            reply_markup=confirmation_keyboard(conf_id),
        )
    except Exception as e:
        logger.warning("Could not send confirmation to employee: %s", e)
        await update.message.reply_text("⚠️ نتوانستیم به کارمند پیام بدهیم.")

    context.user_data.pop("pending_submission_id", None)
    return ConversationHandler.END


async def cancel_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("pending_submission_id", None)
    await update.message.reply_text("لغو شد.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def confirmation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data
    conf_id = int(data.split(":")[1])
    conf = db.get_confirmation(conf_id)

    if not conf or conf["status"] != "pending":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("این پیشنهاد دیگر معتبر نیست.")
        return

    if query.from_user.id != conf["telegram_id"]:
        await query.message.reply_text("این پیشنهاد برای شما نیست.")
        return

    emp = db.get_employee_by_id(conf["telegram_id"])
    name = emp["name"] if emp else "کارمند"
    amount = conf["amount"]
    type_ = conf["type"]
    sign = "+" if amount > 0 else ""
    type_fa = {"wage": "حقوق", "bonus": "پاداش", "fine": "جریمه", "pay": "پرداخت"}.get(type_, type_)

    if data.startswith("conf_accept:"):
        db.accept_confirmation(conf_id)
        new_balance = db.update_balance(conf["telegram_id"], amount)
        db.add_transaction(
            telegram_id=conf["telegram_id"],
            amount=amount,
            type_=type_,
            note=conf["note"],
            submission_id=conf["submission_id"],
        )

        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"✅ شما {type_fa} را تأیید کردید.\n"
            f"مبلغ: *{sign}{amount:.2f}*\n"
            f"موجودی جدید: *{new_balance:.2f}*",
            parse_mode="Markdown",
            reply_markup=employee_keyboard(),
        )

        await notify_admins(
            context,
            f"✅ *{name}* {type_fa} به مبلغ *{sign}{amount:.2f}* را تأیید کرد.\n"
            f"موجودی جدید: *{new_balance:.2f}*",
            parse_mode="Markdown",
        )

    elif data.startswith("conf_decline:"):
        db.decline_confirmation(conf_id)

        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"❌ شما {type_fa} به مبلغ *{sign}{amount:.2f}* را رد کردید.",
            parse_mode="Markdown",
            reply_markup=employee_keyboard(),
        )

        await notify_admins(
            context,
            f"❌ *{name}* {type_fa} به مبلغ *{sign}{amount:.2f}* را رد کرد.\n"
            "هیچ تغییری در موجودی ایجاد نشد.",
            parse_mode="Markdown",
        )


async def register_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("فقط مدیر.")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "استفاده:\n`/register <آیدی> <نام کامل>`\n\n"
            "مثال: `/register 123456789 علی رضایی`",
            parse_mode="Markdown",
        )
        return

    try:
        telegram_id = int(args[0])
    except ValueError:
        await update.message.reply_text("آیدی باید عدد باشد.")
        return

    name = " ".join(args[1:]).strip()
    if not name:
        await update.message.reply_text("نام نمی‌تواند خالی باشد.")
        return

    if db.get_employee_by_id(telegram_id):
        await update.message.reply_text("این آیدی قبلاً ثبت شده.")
        return
    if db.get_employee_by_name(name):
        await update.message.reply_text(f"نام '{name}' قبلاً گرفته شده.")
        return

    ok = db.add_employee(telegram_id, name)
    if not ok:
        await update.message.reply_text("ثبت‌نام ناموفق بود.")
        return

    db.delete_pending_registration(telegram_id)

    await update.message.reply_text(
        f"✅ *{name}* با آیدی `{telegram_id}` ثبت شد.",
        parse_mode="Markdown",
    )

    try:
        await context.bot.send_message(
            chat_id=telegram_id,
            text=(
                f"🎉 شما با نام *{name}* ثبت‌نام شدید!\n\n"
                "حالا می‌توانید عکس یا متن کار خود را بفرستید."
            ),
            parse_mode="Markdown",
            reply_markup=employee_keyboard(),
        )
    except Exception:
        await update.message.reply_text("(نتوانستیم به کارمند پیام بدهیم)")


async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("فقط مدیر.")
        return

    employees = db.list_employees()
    if not employees:
        await update.message.reply_text("هنوز کارمندی ثبت نشده.")
        return

    lines = ["👥 *لیست کارمندان:*"]
    for e in employees:
        lines.append(f"• *{e['name']}* – موجودی: {e['balance']:.2f} (آیدی `{e['telegram_id']}`)")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("فقط مدیر.")
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            "استفاده:\n`/delete <نام>`\n\n"
            "مثال: `/delete علی رضایی`\n\n"
            "⚠️ این کار کارمند و تمام تاریخچه او را برای همیشه حذف می‌کند.",
            parse_mode="Markdown",
        )
        return

    name = " ".join(args).strip()
    emp = db.get_employee_by_name(name)
    if not emp:
        await update.message.reply_text(
            f"کارمند *{name}* پیدا نشد. از /list استفاده کنید.",
            parse_mode="Markdown",
        )
        return

    ok = db.delete_employee(emp["telegram_id"])
    if ok:
        await update.message.reply_text(
            f"🗑️ کارمند *{emp['name']}* حذف شد.\n"
            f"(موجودی قبلی: {emp['balance']:.2f})",
            parse_mode="Markdown",
        )
        try:
            await context.bot.send_message(
                chat_id=emp["telegram_id"],
                text="ℹ️ شما توسط مدیر از سیستم حقوق حذف شدید.",
            )
        except Exception:
            pass
    else:
        await update.message.reply_text("حذف ناموفق بود.")


async def bonus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _direct_adjustment(update, context, type_="bonus", positive=True)


async def fine_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _direct_adjustment(update, context, type_="fine", positive=False)


async def pay_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _direct_adjustment(update, context, type_="pay", positive=False)


async def _direct_adjustment(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    type_: str,
    positive: bool,
) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("فقط مدیر.")
        return

    args = context.args
    type_fa = {"bonus": "پاداش", "fine": "جریمه", "pay": "پرداخت"}
    if len(args) < 2:
        await update.message.reply_text(
            f"استفاده:\n`/{type_} <نام> <مبلغ> [یادداشت]`\n\n"
            f"مثال: `/{type_} علی 50`",
            parse_mode="Markdown",
        )
        return

    name = None
    amount_str = None
    note_parts = []

    for i in range(len(args) - 1, 0, -1):
        possible_name = " ".join(args[:i])
        emp = db.get_employee_by_name(possible_name)
        if emp:
            name = emp["name"]
            amount_str = args[i]
            note_parts = args[i + 1 :]
            break

    if not name:
        await update.message.reply_text("کارمند پیدا نشد. از /list استفاده کنید.")
        return

    try:
        amount = float(amount_str.replace(",", "."))
        if amount <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await update.message.reply_text("مبلغ باید عدد مثبت باشد.")
        return

    if not positive:
        amount = -amount

    note = " ".join(note_parts) if note_parts else None
    emp = db.get_employee_by_name(name)

    new_balance = db.update_balance(emp["telegram_id"], amount)
    db.add_transaction(
        telegram_id=emp["telegram_id"],
        amount=amount,
        type_=type_,
        note=note,
    )

    sign = "+" if amount > 0 else ""
    tname = type_fa.get(type_, type_)
    emoji = {"bonus": "🎁", "fine": "⚠️", "pay": "💵"}.get(type_, "💰")

    await update.message.reply_text(
        f"{emoji} *{tname}* برای *{name}* اعمال شد\n"
        f"مبلغ: *{sign}{amount:.2f}*\n"
        f"موجودی جدید: *{new_balance:.2f}*"
        + (f"\nیادداشت: {note}" if note else ""),
        parse_mode="Markdown",
    )

    try:
        msg = (
            f"{emoji} مدیر یک *{tname}* اعمال کرد:\n"
            f"مبلغ: *{sign}{amount:.2f}*\n"
            f"موجودی جدید: *{new_balance:.2f}*"
        )
        if note:
            msg += f"\nیادداشت: {note}"
        await context.bot.send_message(
            chat_id=emp["telegram_id"],
            text=msg,
            parse_mode="Markdown",
            reply_markup=employee_keyboard(),
        )
    except Exception:
        pass


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if is_admin(user.id):
        text = (
            "*دستورات مدیر:*\n"
            "/list – لیست کارمندان و موجودی\n"
            "/delete `<نام>` – حذف کارمند\n"
            "/bonus `<نام>` `<مبلغ>` – پاداش\n"
            "/fine `<نام>` `<مبلغ>` – جریمه\n"
            "/pay `<نام>` `<مبلغ>` – پرداخت (کم کردن موجودی)\n"
            "/register `<آیدی>` `<نام>` – ثبت دستی\n\n"
            "وقتی کسی /start بزند و نام بفرستد، دکمه قبول/رد می‌گیرید.\n"
            "وقتی گزارش کار بفرستد → تأیید → مبلغ → کارمند هم تأیید می‌کند."
        )
    else:
        text = (
            "*راهنما:*\n\n"
            "• از دکمه‌های پایین صفحه استفاده کنید\n"
            "• عکس یا متن کار خود را بفرستید\n"
            "• 💰 موجودی → دیدن موجودی\n"
            "• 📜 تاریخچه → دیدن تراکنش‌ها\n\n"
            "برای ثبت‌نام /start را بزنید."
        )
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=employee_keyboard() if not is_admin(user.id) else None,
    )


def main() -> None:
    db.init_db()

    application = Application.builder().token(BOT_TOKEN).build()

    reg_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name),
                CommandHandler("cancel", cancel_name),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_name)],
        allow_reentry=True,
        per_message=False,
    )

    amount_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern=r"^(approve|reject):")],
        states={
            WAITING_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_amount),
                CommandHandler("cancel", cancel_amount),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_amount)],
        allow_reentry=True,
        per_message=False,
    )

    application.add_handler(reg_conv)
    application.add_handler(amount_conv)

    application.add_handler(
        CallbackQueryHandler(registration_handler, pattern=r"^reg_(accept|reject):")
    )
    application.add_handler(
        CallbackQueryHandler(confirmation_handler, pattern=r"^conf_(accept|decline):")
    )

    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("balance", balance_cmd))
    application.add_handler(CommandHandler("history", history_cmd))
    application.add_handler(CommandHandler("register", register_cmd))
    application.add_handler(CommandHandler("list", list_cmd))
    application.add_handler(CommandHandler("delete", delete_cmd))
    application.add_handler(CommandHandler("bonus", bonus_cmd))
    application.add_handler(CommandHandler("fine", fine_cmd))
    application.add_handler(CommandHandler("pay", pay_cmd))

    application.add_handler(
        MessageHandler(
            (filters.PHOTO | (filters.TEXT & ~filters.COMMAND)) & filters.ChatType.PRIVATE,
            handle_work_proof,
        )
    )

    logger.info("ربات شروع به کار کرد...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
