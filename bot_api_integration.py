# ==================== API INTEGRATION SECTION ====================
# أضيف هاد الكود في ملف الـ Bot ديالك (ccbb-2.py)

import aiohttp
import asyncio
from typing import Optional, Dict, Any

# ==================== API CONFIG ====================
# استبدل URL بـ URL ديالك من Railway
API_BASE_URL = os.getenv("API_BASE_URL", "https://your-railway-app.up.railway.app")

class PaymentAPIClient:
    """Client للـ API ديالك"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=30)
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """الحصول على HTTP Session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self.session
    
    async def close(self):
        """إغلاق الـ Session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    # ========== CUSTOMER ENDPOINTS ==========
    
    async def create_customer(self, name: str, email: str, phone: str = "") -> Dict[Any, Any]:
        """إنشاء عميل جديد"""
        try:
            session = await self._get_session()
            data = {
                "name": name,
                "email": email,
                "phone": phone
            }
            async with session.post(
                f"{self.base_url}/api/customers",
                json=data
            ) as resp:
                if resp.status == 201:
                    return await resp.json()
                else:
                    error = await resp.json()
                    return {"status": "error", "message": error.get("message", "Failed to create customer")}
        except asyncio.TimeoutError:
            return {"status": "error", "message": "Request timeout"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def get_customer(self, customer_id: int) -> Dict[Any, Any]:
        """الحصول على بيانات العميل"""
        try:
            session = await self._get_session()
            async with session.get(
                f"{self.base_url}/api/customers/{customer_id}"
            ) as resp:
                return await resp.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    # ========== CARD ENDPOINTS ==========
    
    async def add_card(self, customer_id: int, name: str, card_number: str, 
                       exp_month: int, exp_year: int, cvc: str, is_default: bool = False) -> Dict[Any, Any]:
        """حفظ بطاقة جديدة"""
        try:
            session = await self._get_session()
            data = {
                "name": name,
                "card_number": card_number,
                "exp_month": exp_month,
                "exp_year": exp_year,
                "cvc": cvc,
                "is_default": is_default
            }
            async with session.post(
                f"{self.base_url}/api/customers/{customer_id}/cards",
                json=data
            ) as resp:
                return await resp.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def list_cards(self, customer_id: int) -> Dict[Any, Any]:
        """إظهار جميع البطاقات المحفوظة"""
        try:
            session = await self._get_session()
            async with session.get(
                f"{self.base_url}/api/customers/{customer_id}/cards"
            ) as resp:
                return await resp.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def delete_card(self, card_id: int) -> Dict[Any, Any]:
        """حذف بطاقة"""
        try:
            session = await self._get_session()
            async with session.delete(
                f"{self.base_url}/api/cards/{card_id}"
            ) as resp:
                return await resp.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    # ========== PAYMENT ENDPOINTS ==========
    
    async def process_payment(self, customer_id: int, payment_method_id: str,
                             amount: float, currency: str = "usd", 
                             description: str = "") -> Dict[Any, Any]:
        """معالجة الدفع"""
        try:
            session = await self._get_session()
            data = {
                "customer_id": customer_id,
                "payment_method_id": payment_method_id,
                "amount": amount,
                "currency": currency,
                "description": description
            }
            async with session.post(
                f"{self.base_url}/api/payments",
                json=data
            ) as resp:
                return await resp.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def get_transactions(self, customer_id: int, page: int = 1, per_page: int = 10) -> Dict[Any, Any]:
        """سجل المعاملات"""
        try:
            session = await self._get_session()
            async with session.get(
                f"{self.base_url}/api/customers/{customer_id}/transactions",
                params={"page": page, "per_page": per_page}
            ) as resp:
                return await resp.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def refund(self, transaction_id: int, amount: float = None, reason: str = "requested_by_customer") -> Dict[Any, Any]:
        """استرجاع مبلغ"""
        try:
            session = await self._get_session()
            data = {
                "reason": reason
            }
            if amount:
                data["amount"] = amount
            async with session.post(
                f"{self.base_url}/api/transactions/{transaction_id}/refund",
                json=data
            ) as resp:
                return await resp.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def get_config(self) -> Dict[Any, Any]:
        """الحصول على Stripe Config"""
        try:
            session = await self._get_session()
            async with session.get(
                f"{self.base_url}/api/config"
            ) as resp:
                return await resp.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ==================== GLOBAL API CLIENT ====================
api_client = PaymentAPIClient(API_BASE_URL)


# ==================== BOT COMMANDS - PAYMENT INTEGRATION ====================

@client.on(events.NewMessage(pattern=r'(?i)^[/.]payment$'))
async def payment_menu_cmd(event):
    """قائمة الدفع"""
    uid = event.sender_id
    await ensure_user(uid)
    
    buttons = [
        [Button.inline("💳 Add Card", data=b"add_card")],
        [Button.inline("💰 Make Payment", data=b"make_payment")],
        [Button.inline("📊 Transaction History", data=b"trans_history")],
        [Button.inline("🔄 Refund", data=b"refund_payment")],
        [Button.inline("❌ Cancel", data=b"cancel")],
    ]
    
    await event.reply(
        f"{PE} <b>{bs('Payment Menu')} 💳</b>\n\n"
        f"اختر الخدمة الي تبغيها:",
        buttons=buttons
    )


@client.on(events.CallbackQuery(data=b"add_card"))
async def add_card_callback(event):
    """إضافة بطاقة"""
    uid = event.sender_id
    await event.edit(
        f"{PE} <b>{bs('Add Card')} 💳</b>\n\n"
        f"<b>الرجاء إرسال البيانات بهذا الشكل:</b>\n"
        f"<code>name|card_number|exp_month|exp_year|cvc</code>\n\n"
        f"<b>مثال:</b>\n"
        f"<code>Ahmed Ali|4242424242424242|12|2025|123</code>"
    )
    
    # Save state
    PENDING_ADD_SITES[uid] = "awaiting_card_data"


@client.on(events.NewMessage())
async def handle_card_input(event):
    """معالجة إدخال بيانات البطاقة"""
    uid = event.sender_id
    
    if PENDING_ADD_SITES.get(uid) != "awaiting_card_data":
        return
    
    try:
        data = event.message.text.split("|")
        if len(data) != 5:
            return await event.reply(
                f"❌ صيغة خاطئة! استخدم:\n"
                f"<code>name|card_number|exp_month|exp_year|cvc</code>"
            )
        
        name, card_number, exp_month, exp_year, cvc = data
        exp_month = int(exp_month)
        exp_year = int(exp_year)
        
        # Get customer from DB
        user = await db["users"].find_one({"user_id": uid})
        if not user or not user.get("customer_id"):
            # Create customer first
            email = f"user_{uid}@payment.local"
            customer_resp = await api_client.create_customer(
                name=name,
                email=email,
                phone=""
            )
            
            if customer_resp.get("status") != "success":
                return await event.reply(f"❌ Error: {customer_resp.get('message')}")
            
            customer_id = customer_resp["customer"]["id"]
            await db["users"].update_one(
                {"user_id": uid},
                {"$set": {"customer_id": customer_id}}
            )
        else:
            customer_id = user.get("customer_id")
        
        # Add card
        wait_msg = await event.reply("⏳ جاري إضافة البطاقة...")
        card_resp = await api_client.add_card(
            customer_id=customer_id,
            name=name,
            card_number=card_number,
            exp_month=exp_month,
            exp_year=exp_year,
            cvc=cvc,
            is_default=True
        )
        
        if card_resp.get("status") == "success":
            card = card_resp["card"]
            await wait_msg.edit(
                f"✅ <b>تمت إضافة البطاقة!</b>\n\n"
                f"{PE} <b>Brand:</b> <code>{card['brand']}</code>\n"
                f"{PE} <b>Last 4:</b> <code>{card['last4']}</code>\n"
                f"{PE} <b>Expiry:</b> <code>{card['expiry']}</code>"
            )
            # Save card to DB
            await db["users"].update_one(
                {"user_id": uid},
                {"$set": {"saved_card_id": card["stripe_payment_method_id"]}}
            )
        else:
            await wait_msg.edit(f"❌ Error: {card_resp.get('message')}")
        
        del PENDING_ADD_SITES[uid]
        
    except Exception as e:
        await event.reply(f"❌ Error: {str(e)}")
        del PENDING_ADD_SITES[uid]


@client.on(events.CallbackQuery(data=b"make_payment"))
async def make_payment_callback(event):
    """عمل دفع"""
    uid = event.sender_id
    user = await db["users"].find_one({"user_id": uid})
    
    if not user or not user.get("saved_card_id"):
        return await event.answer("❌ ليس لديك بطاقة محفوظة! أضف واحدة أولاً", alert=True)
    
    await event.edit(
        f"{PE} <b>{bs('Make Payment')} 💰</b>\n\n"
        f"<b>أدخل المبلغ (بالدولار):</b>\n"
        f"<i>مثال: 49.99</i>"
    )
    
    PENDING_ADD_SITES[uid] = "awaiting_amount"


@client.on(events.NewMessage())
async def handle_payment_amount(event):
    """معالجة مبلغ الدفع"""
    uid = event.sender_id
    
    if PENDING_ADD_SITES.get(uid) != "awaiting_amount":
        return
    
    try:
        amount = float(event.message.text)
        if amount < 0.50:
            return await event.reply("❌ المبلغ يجب أن يكون أكثر من 0.50$")
        
        user = await db["users"].find_one({"user_id": uid})
        customer_id = user.get("customer_id")
        payment_method_id = user.get("saved_card_id")
        
        wait_msg = await event.reply("⏳ جاري معالجة الدفع...")
        
        payment_resp = await api_client.process_payment(
            customer_id=customer_id,
            payment_method_id=payment_method_id,
            amount=amount,
            currency="usd",
            description=f"Payment from Telegram user {uid}"
        )
        
        if payment_resp.get("status") == "success":
            trans = payment_resp["transaction"]
            await wait_msg.edit(
                f"✅ <b>تم الدفع بنجاح!</b>\n\n"
                f"{PE} <b>Amount:</b> <code>${trans['amount']}</code>\n"
                f"{PE} <b>Currency:</b> <code>{trans['currency']}</code>\n"
                f"{PE} <b>Status:</b> <code>{trans['status']}</code>\n"
                f"{PE} <b>Transaction ID:</b> <code>{trans['stripe_payment_intent_id']}</code>"
            )
            
            # Log to hit channel
            if LOG_CHANNEL_ID:
                try:
                    await client_instance.send_message(
                        LOG_CHANNEL_ID,
                        f"💰 <b>New Payment</b>\n\n"
                        f"User: <code>{uid}</code>\n"
                        f"Amount: <code>${amount}</code>\n"
                        f"Status: <code>{trans['status']}</code>",
                        parse_mode='html'
                    )
                except:
                    pass
        else:
            await wait_msg.edit(f"❌ Error: {payment_resp.get('message')}")
        
        del PENDING_ADD_SITES[uid]
        
    except ValueError:
        await event.reply("❌ أدخل رقم صحيح!")
    except Exception as e:
        await event.reply(f"❌ Error: {str(e)}")
        del PENDING_ADD_SITES[uid]


@client.on(events.CallbackQuery(data=b"trans_history"))
async def trans_history_callback(event):
    """سجل المعاملات"""
    uid = event.sender_id
    user = await db["users"].find_one({"user_id": uid})
    
    if not user or not user.get("customer_id"):
        return await event.answer("❌ لا توجد معاملات بعد", alert=True)
    
    customer_id = user.get("customer_id")
    trans_resp = await api_client.get_transactions(customer_id, page=1, per_page=10)
    
    if trans_resp.get("status") != "success":
        return await event.answer(f"❌ {trans_resp.get('message')}", alert=True)
    
    transactions = trans_resp.get("transactions", [])
    if not transactions:
        return await event.answer("❌ لا توجد معاملات", alert=True)
    
    msg = f"{PE} <b>{bs('Transaction History')} 📊</b>\n\n"
    for trans in transactions:
        msg += (
            f"<b>━━━━━━━━━━━━━</b>\n"
            f"{PE} <b>Amount:</b> <code>${trans['amount']}</code>\n"
            f"{PE} <b>Status:</b> <code>{trans['status']}</code>\n"
            f"{PE} <b>Date:</b> <code>{trans['created_at']}</code>\n"
        )
    
    await event.edit(msg)


@client.on(events.CallbackQuery(data=b"cancel"))
async def cancel_callback(event):
    """إلغاء"""
    await event.delete()


# ==================== CLEANUP ====================
# أضيف هاد في الـ main() function

async def cleanup_api():
    """إغلاق API Client عند إيقاف البوت"""
    await api_client.close()


# عدّل الـ main function:
# async def main():
#     try:
#         ...
#     finally:
#         await cleanup_api()
