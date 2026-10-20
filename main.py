import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta

BOT_TOKEN = "8619414112:AAG7gAZjduitlSnx3_gz5KMm2nUNmqZ2zaQ"
MERCHANT_ID = 6078183074  # أيدي التاجر (صاحب المتجر)
ADMIN_CONTACT = "@YourSupportUsername" # معرف حسابك أنت (المطور)

bot = telebot.TeleBot(BOT_TOKEN)
user_state = {}

# --- 1. إعداد قاعدة البيانات وتجهيز الجداول ---
def init_db():
    conn = sqlite3.connect('digital_store.db')
    c = conn.cursor()
    # جدول الاشتراك الشهري للمتجر
    c.execute('''CREATE TABLE IF NOT EXISTS subscription
                 (id INTEGER PRIMARY KEY, expiry_date TEXT, is_active INTEGER)''')
    # جدول المنتجات الرقمية (ألعاب، بطاقات...)
    c.execute('''CREATE TABLE IF NOT EXISTS products
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price REAL)''')
    # جدول محافظ المستخدمين (الرصيد والمعرف)
    c.execute('''CREATE TABLE IF NOT EXISTS wallets
                 (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0, username TEXT)''')
    
    # تجربة مجانية للمتجر وإضافة منتجات افتراضية عند التشغيل الأول
    c.execute("SELECT COUNT(*) FROM subscription")
    if c.fetchone()[0] == 0:
        trial_end = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
        c.execute("INSERT INTO subscription (id, expiry_date, is_active) VALUES (1, ?, 1)", (trial_end,))
        c.execute("INSERT INTO products (name, price) VALUES ('ببجي - 60 شدة', 1.0)")
        c.execute("INSERT INTO products (name, price) VALUES ('فري فاير - 100 جوهرة', 1.0)")
        c.execute("INSERT INTO products (name, price) VALUES ('بطاقة جوجل بلاي 10$', 10.0)")
        
    conn.commit()
    conn.close()

init_db()

# --- 2. فحص حالة اشتراك المتجر ---
def check_subscription():
    conn = sqlite3.connect('digital_store.db')
    c = conn.cursor()
    c.execute("SELECT expiry_date, is_active FROM subscription WHERE id = 1")
    sub = c.fetchone()
    conn.close()
    if not sub or sub[1] == 0:
        return False
    expiry_date = datetime.strptime(sub[0], '%Y-%m-%d')
    if datetime.now() > expiry_date:
        return False
    return True

# --- 3. الواجهة الرئيسية للبوت ---
@bot.message_handler(commands=['start'])
def start_store(message):
    if not check_subscription():
        if message.from_user.id == MERCHANT_ID:
            bot.send_message(message.chat.id, f"⚠️ تنبيه للإدارة: انتهى اشتراك متجرك. تواصل مع المطور عبر {ADMIN_CONTACT} للتجديد.")
        else:
            bot.send_message(message.chat.id, "عذراً، المتجر مغلق للصيانة حالياً. يرجى العودة لاحقاً.")
        return

    user_id = message.from_user.id
    username = message.from_user.first_name

    # تسجيل المحفظة تلقائياً للزبون الجديد
    conn = sqlite3.connect('digital_store.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO wallets (user_id, balance, username) VALUES (?, 0.0, ?)", (user_id, username))
    conn.commit()
    conn.close()

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🛒 تصفح المنتجات وشحن الألعاب", callback_data="view_shop"),
        types.InlineKeyboardButton("💰 محفظتي الرصيد والشحن", callback_data="my_wallet"),
        types.InlineKeyboardButton("📞 الدعم الفني", callback_data="support")
    )

    if user_id == MERCHANT_ID:
        markup.add(types.InlineKeyboardButton("⚙️ لوحة إدارة المتجر (للتاجر)", callback_data="admin_panel"))

    bot.send_message(message.chat.id, f"🎮 **أهلاً بك يا {username} في متجر الشحن الرقمي!**\nاختر من القائمة أدناه:", reply_markup=markup, parse_mode="Markdown")

# --- 4. نظام إدارة المحفظة للزبون ---
@bot.callback_query_handler(func=lambda call: call.data == "my_wallet")
def show_wallet(call):
    user_id = call.from_user.id
    conn = sqlite3.connect('digital_store.db')
    c = conn.cursor()
    c.execute("SELECT balance FROM wallets WHERE user_id = ?", (user_id,))
    res = c.fetchone()
    conn.close()
    
    balance = res[0] if res else 0.0

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📥 كيفية شحن الرصيد", callback_data="recharge_info"),
        types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")
    )

    bot.edit_message_text(f"💰 **محفظتك الرقمية:**\n\nرصيدك الحالي: **{balance}$**\n\nاشحن رصيدك واستمتع بالشراء الفوري بضغطة زر واحدة!",
                          call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "recharge_info")
def recharge_info(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 رجوع للمحفظة", callback_data="my_wallet"))
    bot.edit_message_text("📥 **طريقة شحن الرصيد:**\n\nقم بتحويل المبلغ المطلوب للدعم، ثم أرسل إيصال التحويل مع الآي دي الخاص بك إلى حساب الإدارة: " + ADMIN_CONTACT + "\nليقوم المشرف بإضافة الرصيد إلى محفظتك فوراً.",
                          call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# --- 5. أوامر التاجر لإضافة رصيد للمستخدمين ---
# صيغة الأمر: /add_balance [User_ID] [المبلغ]
@bot.message_handler(commands=['add_balance'])
def add_user_balance(message):
    if message.from_user.id != MERCHANT_ID:
        return
    
    try:
        parts = message.text.split()
        target_user_id = int(parts[1])
        amount = float(parts[2])

        conn = sqlite3.connect('digital_store.db')
        c = conn.cursor()
        c.execute("UPDATE wallets SET balance = balance + ? WHERE user_id = ?", (amount, target_user_id))
        conn.commit()
        conn.close()

        bot.reply_to(message, f"✅ تم إضافة {amount}$ بنجاح إلى محفظة المستخدم (ID: {target_user_id})")
        bot.send_message(target_user_id, f"🎉 **تم شحن محفظتك بنجاح!**\nتم إضافة رصيد بقيمة: **{amount}$** إلى حسابك.")
    except Exception:
        bot.reply_to(message, "⚠️ خطأ في الصيغة! استخدم الأمر هكذا:\n`/add_balance [ID_المستخدم] [المبلغ]`", parse_mode="Markdown")

# --- 6. تصفح المنتجات والشراء التلقائي من المحفظة ---
@bot.callback_query_handler(func=lambda call: call.data == "view_shop")
def show_shop(call):
    conn = sqlite3.connect('digital_store.db')
    c = conn.cursor()
    c.execute("SELECT id, name, price FROM products")
    products = c.fetchall()
    conn.close()

    markup = types.InlineKeyboardMarkup(row_width=1)
    for prod in products:
        markup.add(types.InlineKeyboardButton(f"{prod[1]} - السعر: {prod[2]}$", callback_data=f"buy_{prod[0]}"))
    
    markup.add(types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu"))
    bot.edit_message_text("📦 **اختر المنتج المطلوب شراؤه:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def process_buy(call):
    product_id = call.data.split("_")[1]
    
    conn = sqlite3.connect('digital_store.db')
    c = conn.cursor()
    c.execute("SELECT name, price FROM products WHERE id = ?", (product_id,))
    prod = c.fetchone()
    conn.close()

    user_state[call.from_user.id] = {"product": prod[0], "price": prod[1]}

    bot.edit_message_text(f"🛍️ لقد اخترت: **{prod[0]}** (السعر: {prod[1]}$)\n\n✍️ **أدخل الآن (الـ ID الخاص بك داخل اللعبة أو البريد المطلوب شحنه):**", 
                          call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    bot.register_next_step_handler(call.message, execute_purchase)

def execute_purchase(message):
    user_id = message.from_user.id
    if user_id not in user_state:
        return
    
    p_info = message.text
    p_name = user_state[user_id]["product"]
    p_price = user_state[user_id]["price"]

    conn = sqlite3.connect('digital_store.db')
    c = conn.cursor()
    c.execute("SELECT balance FROM wallets WHERE user_id = ?", (user_id,))
    res = c.fetchone()
    balance = res[0] if res else 0.0

    if balance < p_price:
        bot.send_message(message.chat.id, f"❌ **رصيدك غير كافٍ!**\nرصيدك الحالي: {balance}$ \vert{} سعر المنتج: {p_price}$\nيرجى شحن محفظتك أولاً.")
        del user_state[user_id]
        return

    # خصم السعر من المحفظة
    new_balance = balance - p_price
    c.execute("UPDATE wallets SET balance = ? WHERE user_id = ?", (new_balance, user_id))
    conn.commit()
    conn.close()

    customer_username = f"@{message.from_user.username}" if message.from_user.username else f"ID: {user_id}"
    order_text = (
        f"🚨 **طلب جديد مدفوع من المحفظة!**\n\n"
        f"📦 المنتج: {p_name} ({p_price}$)\n"
        f"🎯 بيانات الشحن (ID): {p_info}\n"
        f"👤 الزبون: {customer_username}"
    )
    bot.send_message(MERCHANT_ID, order_text, parse_mode="Markdown")

    bot.send_message(message.chat.id, f"✅ **تم الشراء بنجاح!**\nتم خصم {p_price}$ من محفظتك. رصيدك المتبقي: **{new_balance}$**\nسيتم تنفيذ الشحن وإرساله لك في أقرب وقت.")
    del user_state[user_id]

# --- 7. لوحة تحكم التاجر داخل البوت ---
@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def admin_panel(call):
    if call.from_user.id != MERCHANT_ID:
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➕ إضافة منتج جديد", callback_data="add_prod_step"),
        types.InlineKeyboardButton("📋 عرض المنتجات الحالية", callback_data="list_prod"),
        types.InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")
    )
    bot.edit_message_text("⚙️ **لوحة إدارة المتجر:**\nتحكم بمنتجات متجرك الرقمي بسهولة:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "add_prod_step")
def add_prod_step(call):
    if call.from_user.id != MERCHANT_ID:
        return
    bot.edit_message_text("✍️ أرسل تفاصيل المنتج الجديد بهذا الشكل تماماً:\n`اسم المنتج, السعر`\n\nمثال:\n`ببجي - 300 شدة, 5.0`", 
                          call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    bot.register_next_step_handler(call.message, save_new_product)

def save_new_product(message):
    if message.from_user.id != MERCHANT_ID:
        return
    try:
        parts = message.text.split(",")
        name = parts[0].strip()
        price = float(parts[1].strip())

        conn = sqlite3.connect('digital_store.db')
        c = conn.cursor()
        c.execute("INSERT INTO products (name, price) VALUES (?, ?)", (name, price))
        conn.commit()
        conn.close()

        bot.reply_to(message, f"✅ تمت إضافة المنتج بنجاح: **{name}** بسعر **{price}$**", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "⚠️ حدث خطأ في الصيغة! تأكد من كتابة الاسم ثم فاصلة `,` ثم السعر الرقمي.")

@bot.callback_query_handler(func=lambda call: call.data == "list_prod")
def list_products(call):
    if call.from_user.id != MERCHANT_ID:
        return
    
    conn = sqlite3.connect('digital_store.db')
    c = conn.cursor()
    c.execute("SELECT id, name, price FROM products")
    products = c.fetchall()
    conn.close()

    text = "📋 **قائمة منتجات متجرك:**\n\n"
    for p in products:
        text += f"🆔 `ID: {p[0]}` | {p[1]} - **{p[2]}$**\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 لوحة التحكم", callback_data="admin_panel"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "main_menu" or call.data == "support")
def back_home(call):
    if call.data == "support":
        bot.answer_callback_query(call.id, f"للدعم الفني تواصل مع: {ADMIN_CONTACT}", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🛒 تصفح المنتجات وشحن الألعاب", callback_data="view_shop"),
        types.InlineKeyboardButton("💰 محفظتي الرصيد والشحن", callback_data="my_wallet"),
        types.InlineKeyboardButton("📞 الدعم الفني", callback_data="support")
    )
    if call.from_user.id == MERCHANT_ID:
        markup.add(types.InlineKeyboardButton("⚙️ لوحة إدارة المتجر (للتاجر)", callback_data="admin_panel"))

    bot.edit_message_text("🎮 **القائمة الرئيسية:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

bot.polling(none_stop=True)
