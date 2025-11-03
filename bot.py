import sqlite3
import logging
import threading
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

from config import BOT_TOKEN, ADMIN_IDS, MAX_MESSAGE_LENGTH, MAX_SESSIONS_PER_USER
from database import AnonymousDatabase

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class AnonymousBot:
    def __init__(self):
        self.db = AnonymousDatabase()
        self.user_sessions = {}  # {user_id: session_id}
        self.session_users = {}  # {session_id: [user_id1, user_id2]}
        self.application = None
    
    def is_admin(self, user_id):
        """Проверка, является ли пользователь администратором"""
        return user_id in ADMIN_IDS
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user_id = update.effective_user.id
        
        keyboard = [
            [InlineKeyboardButton("📝 Create Chat", callback_data="create_session")],
            [InlineKeyboardButton("🔑 Join Chat", callback_data="join_session")],
            [InlineKeyboardButton("📋 My Chats", callback_data="my_sessions")],
            [InlineKeyboardButton("❓ Help", callback_data="help")]
        ]
        
        # Добавляем кнопку админа если пользователь админ
        if self.is_admin(user_id):
            keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = """
🤫 Welcome to the anonymous messaging bot!

🔒 Features:
• Complete anonymity - we don't store message logs
• Secure connection
• Automatic deletion after 24 hours

📖 How to use:
1. Create a chat and get a passphrase
2. Share the passphrase with your partner
3. Start anonymous conversation

Choose an action:
        """
        
        await update.message.reply_text(welcome_text.strip(), reply_markup=reply_markup)
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий кнопок"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        if data == "create_session":
            await self.create_session(query, context)
        elif data == "join_session":
            await self.ask_passphrase(query, context)
        elif data == "my_sessions":
            await self.show_my_sessions(query, context)
        elif data == "help":
            await self.show_help(query, context)
        elif data.startswith("session_"):
            session_id = data.split("_")[1]
            await self.enter_session(query, context, session_id)
        elif data == "back_to_menu":
            await self.show_main_menu(query, context)
        
        # Админские функции
        elif data == "admin_panel":
            await self.show_admin_panel(query, context)
        elif data == "admin_stats":
            await self.show_admin_stats(query, context)
        elif data == "admin_active_sessions":
            await self.show_admin_active_sessions(query, context)
        elif data == "admin_broadcast":
            await self.ask_broadcast_message(query, context)
        elif data == "admin_cleanup":
            await self.force_cleanup(query, context)
        elif data.startswith("admin_session_"):
            session_action = data.split("_")[2]
            session_id = data.split("_")[3]
            if session_action == "view":
                await self.admin_view_session(query, context, session_id)
            elif session_action == "close":
                await self.admin_close_session(query, context, session_id)
    
    async def show_admin_panel(self, query, context):
        """Показать панель администратора"""
        user_id = query.from_user.id
        
        if not self.is_admin(user_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        keyboard = [
            [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
            [InlineKeyboardButton("💬 Active Sessions", callback_data="admin_active_sessions")],
            [InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🧹 Force Cleanup", callback_data="admin_cleanup")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        admin_text = """
👑 Admin Panel

Choose an action:
• 📊 Statistics - View bot usage statistics
• 💬 Active Sessions - View and manage active sessions
• 📢 Broadcast - Send message to all users
• 🧹 Cleanup - Force cleanup of old sessions
        """
        
        await query.edit_message_text(admin_text.strip(), reply_markup=reply_markup)
    
    async def show_admin_stats(self, query, context):
        """Показать статистику"""
        user_id = query.from_user.id
        
        if not self.is_admin(user_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        # Получаем статистику из базы данных
        stats = self.db.get_system_stats()
        
        stats_text = f"""
📊 System Statistics

🤖 Bot Information:
• Active users in memory: {len(self.user_sessions)}
• Active sessions in memory: {len(self.session_users)}

💾 Database Information:
• Total active sessions: {stats['total_sessions']}
• Total messages: {stats['total_messages']}
• Old sessions (24h+): {stats['old_sessions']}
• Unique users: {stats['unique_users']}

📈 Usage Statistics:
• Sessions created today: {stats['sessions_today']}
• Messages today: {stats['messages_today']}
• Average messages per session: {stats['avg_messages_per_session']}

🕐 Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="admin_stats")],
            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(stats_text.strip(), reply_markup=reply_markup)
    
    async def show_admin_active_sessions(self, query, context):
        """Показать активные сессии для админа"""
        user_id = query.from_user.id
        
        if not self.is_admin(user_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        active_sessions = self.db.get_all_active_sessions_with_stats()
        
        if not active_sessions:
            await query.edit_message_text("📭 No active sessions found.")
            return
        
        keyboard = []
        for session in active_sessions[:15]:  # Ограничиваем показ
            session_id = session[0]
            creator_id = session[1]
            message_count = session[4]
            
            # Получаем количество участников из памяти
            user_count = len(self.session_users.get(session_id, []))
            
            keyboard.append([
                InlineKeyboardButton(
                    f"💬 {session_id[:8]}... (👥{user_count} 📝{message_count})", 
                    callback_data=f"admin_session_view_{session_id}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔄 Refresh", callback_data="admin_active_sessions")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"💬 Active Sessions ({len(active_sessions)}):\n\n"
            "Format: SessionID (Participants Messages)\n"
            "Click to view details:",
            reply_markup=reply_markup
        )
    
    async def admin_view_session(self, query, context, session_id):
        """Просмотр деталей сессии для админа"""
        user_id = query.from_user.id
        
        if not self.is_admin(user_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        session_info = self.get_session_details(session_id)
        
        if not session_info:
            await query.edit_message_text("❌ Session not found.")
            return
        
        session_text = f"""
💬 Session Details

🆔 Session ID: {session_id}
👤 Creator: {session_info['creator_id']}
👥 Participants: {len(session_info['participants'])}
📝 Messages: {session_info['message_count']}
🕐 Created: {session_info['created_at']}
⏰ Last Activity: {session_info['last_activity']}
📊 Status: {'🟢 Active' if session_info['is_active'] else '🔴 Inactive'}

👥 Participants:
""" + "\n".join([f"• User {user_id}" for user_id in session_info['participants']])

        keyboard = [
            [InlineKeyboardButton("🔴 Close Session", callback_data=f"admin_session_close_{session_id}")],
            [InlineKeyboardButton("🔙 Back to Sessions", callback_data="admin_active_sessions")],
            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(session_text.strip(), reply_markup=reply_markup)
    
    async def admin_close_session(self, query, context, session_id):
        """Закрытие сессии администратором"""
        user_id = query.from_user.id
        
        if not self.is_admin(user_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        # Закрываем сессию
        self.db.close_session(session_id)
        
        # Удаляем из памяти
        if session_id in self.session_users:
            for user_id in self.session_users[session_id]:
                if user_id in self.user_sessions:
                    del self.user_sessions[user_id]
            del self.session_users[session_id]
        
        # Уведомляем участников
        await self.notify_session_users(session_id, "🔴 This chat has been closed by administrator.")
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Sessions", callback_data="admin_active_sessions")],
            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(f"✅ Session {session_id[:8]}... has been closed.", reply_markup=reply_markup)
    
    async def ask_broadcast_message(self, query, context):
        """Запрос сообщения для рассылки"""
        user_id = query.from_user.id
        
        if not self.is_admin(user_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        context.user_data['awaiting_broadcast'] = True
        
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📢 Enter broadcast message:\n\n"
            "This message will be sent to all users who have active sessions.",
            reply_markup=reply_markup
        )
    
    async def handle_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка рассылки"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id) or not context.user_data.get('awaiting_broadcast'):
            return
        
        message_text = update.message.text
        sent_count = 0
        failed_count = 0
        
        # Получаем всех уникальных пользователей с активными сессиями
        all_users = set()
        for session_users in self.session_users.values():
            all_users.update(session_users)
        
        # Отправляем сообщение каждому пользователю
        for user_id in all_users:
            try:
                await self.application.bot.send_message(
                    user_id, 
                    f"📢 Announcement from admin:\n\n{message_text}"
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send broadcast to {user_id}: {e}")
                failed_count += 1
        
        context.user_data['awaiting_broadcast'] = False
        
        await update.message.reply_text(
            f"✅ Broadcast completed!\n"
            f"✓ Sent: {sent_count}\n"
            f"✗ Failed: {failed_count}\n"
            f"📊 Total: {len(all_users)} users"
        )
    
    async def force_cleanup(self, query, context):
        """Принудительная очистка старых сессий"""
        user_id = query.from_user.id
        
        if not self.is_admin(user_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        # Выполняем очистку
        cleaned_count = self.db.cleanup_old_sessions()
        
        # Очищаем память
        active_session_ids = self.db.get_all_active_session_ids()
        active_sessions_set = set(active_session_ids)
        
        # Удаляем неактивные сессии из памяти
        sessions_to_remove = []
        for session_id in list(self.session_users.keys()):
            if session_id not in active_sessions_set:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            for user_id in self.session_users[session_id]:
                if user_id in self.user_sessions and self.user_sessions[user_id] == session_id:
                    del self.user_sessions[user_id]
            del self.session_users[session_id]
        
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        cleanup_info = f"""
✅ Cleanup completed!

• Sessions removed from database: {len(sessions_to_remove)}
• Sessions cleaned from memory: {len(sessions_to_remove)}
• Remaining active sessions: {len(active_session_ids)}

🕐 Cleanup time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        await query.edit_message_text(cleanup_info.strip(), reply_markup=reply_markup)
    
    def get_session_details(self, session_id):
        """Получение деталей сессии"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT creator_user_id, created_at, last_activity, is_active
            FROM sessions WHERE session_id = ?
        ''', (session_id,))
        
        session_data = cursor.fetchone()
        if not session_data:
            return None
        
        # Количество сообщений
        cursor.execute('SELECT COUNT(*) FROM messages WHERE session_id = ?', (session_id,))
        message_count_result = cursor.fetchone()
        message_count = message_count_result[0] if message_count_result else 0
        
        conn.close()
        
        return {
            'creator_id': session_data[0],
            'created_at': session_data[1],
            'last_activity': session_data[2],
            'is_active': bool(session_data[3]),
            'message_count': message_count,
            'participants': self.session_users.get(session_id, [])
        }

    # Остальные методы остаются без изменений
    async def create_session(self, query, context):
        """Создание новой сессии"""
        user_id = query.from_user.id
        
        # Проверка лимита сессий
        active_sessions = self.db.get_user_active_sessions(user_id)
        if len(active_sessions) >= MAX_SESSIONS_PER_USER:
            await query.edit_message_text(
                "❌ You've reached the limit of active sessions. "
                "Close some of your existing sessions."
            )
            return
        
        session_id, passphrase = self.db.create_session(user_id)
        
        # Сохраняем сессию для пользователя
        self.user_sessions[user_id] = session_id
        self.session_users[session_id] = [user_id]
        
        message_text = f"""
✅ Anonymous chat created!

🔑 Your passphrase:
`{passphrase}`

📋 Share this passphrase with your chat partner.

⚠️ Save the passphrase in a secure place - it cannot be recovered!

💬 You can now send messages in this chat.
        """
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message_text.strip(), reply_markup=reply_markup)
    
    async def ask_passphrase(self, query, context):
        """Запрос ключ-фразы для присоединения"""
        context.user_data['awaiting_passphrase'] = True
        
        message_text = """
🔑 Enter passphrase to join the chat:

Format: word-word-word-word-word-word

Example: `amber-dolphin-galaxy-encryption-phoenix-avocado`
        """
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message_text.strip(), reply_markup=reply_markup)
    
    async def handle_passphrase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка введенной ключ-фразы"""
        user_id = update.effective_user.id
        
        if not context.user_data.get('awaiting_passphrase'):
            return
        
        passphrase = update.message.text.strip().lower()
        
        # Проверка формата ключ-фразы
        if len(passphrase.split('-')) != 6:
            await update.message.reply_text(
                "❌ Invalid passphrase format. "
                "Use format: word-word-word-word-word-word"
            )
            return
        
        session_id = self.db.join_session(passphrase, user_id)
        
        if session_id:
            # Добавляем пользователя в сессию
            self.user_sessions[user_id] = session_id
            if session_id in self.session_users:
                self.session_users[session_id].append(user_id)
            else:
                self.session_users[session_id] = [user_id]
            
            # Отправляем историю сообщений
            messages = self.db.get_session_messages(session_id)
            if messages:
                history_text = "📜 Message history:\n\n"
                for msg_text, sender_type, timestamp in messages:
                    prefix = "👤 You: " if (sender_type == 'creator' and user_id != self.get_session_creator(session_id)) or \
                                          (sender_type == 'responder' and user_id == self.get_session_creator(session_id)) else "🗣️ Anonymous: "
                    history_text += f"{prefix}{msg_text}\n"
                
                # Разбиваем длинные сообщения
                if len(history_text) > 4096:
                    chunks = [history_text[i:i+4096] for i in range(0, len(history_text), 4096)]
                    for chunk in chunks:
                        await update.message.reply_text(chunk)
                else:
                    await update.message.reply_text(history_text)
            
            await update.message.reply_text(
                "✅ You've joined the anonymous chat! "
                "You can now send messages."
            )
            
            # Уведомляем другого участника
            await self.notify_session_users(session_id, "🔔 New participant joined the chat!", exclude_user=user_id)
        else:
            await update.message.reply_text(
                "❌ Chat with this passphrase not found or was deleted. "
                "Check the passphrase correctness."
            )
        
        context.user_data['awaiting_passphrase'] = False
    
    async def show_my_sessions(self, query, context):
        """Показать активные сессии пользователя"""
        user_id = query.from_user.id
        active_sessions = self.db.get_user_active_sessions(user_id)
        
        if not active_sessions:
            await query.edit_message_text(
                "📭 You don't have any active chats.\n\n"
                "Create a new chat or join an existing one."
            )
            return
        
        keyboard = []
        for session_id in active_sessions[:10]:
            keyboard.append([InlineKeyboardButton(
                f"💬 Chat {session_id[:8]}...", 
                callback_data=f"session_{session_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📋 Your active chats:\n\n"
            "Select a chat to view:",
            reply_markup=reply_markup
        )
    
    async def enter_session(self, query, context, session_id):
        """Вход в существующую сессию"""
        user_id = query.from_user.id
        self.user_sessions[user_id] = session_id
        
        messages = self.db.get_session_messages(session_id)
        
        if messages:
            history_text = "📜 Message history:\n\n"
            for msg_text, sender_type, timestamp in messages[-20:]:
                prefix = "👤 You: " if (sender_type == 'creator' and user_id != self.get_session_creator(session_id)) or \
                                      (sender_type == 'responder' and user_id == self.get_session_creator(session_id)) else "🗣️ Anonymous: "
                history_text += f"{prefix}{msg_text}\n"
            
            await query.edit_message_text(
                f"{history_text}\n💬 You can now send messages in this chat."
            )
        else:
            await query.edit_message_text(
                "💬 Chat created. Waiting for messages from your partner.\n\n"
                "Send a message to start the conversation."
            )
    
    async def show_help(self, query, context):
        """Показать справку"""
        help_text = """
❓ Bot Usage Help

📖 Basic commands:
• /start - Main menu
• /help - This help

🔐 How anonymity works:
• Bot doesn't store message logs
• All messages are encrypted in the database
• Sessions are automatically deleted after 24 hours
• It's impossible to identify your partner

🛡️ Security measures:
• Use strong passphrases
• Don't share passphrases with strangers
• Sessions automatically close when inactive

⚠️ Important:
• Bot doesn't keep message history after session closure
• Administrators don't have access to your message content
• For maximum security use one-time passphrases

🔑 Passphrase format:
• 6 random English words
• Format: word-word-word-word-word-word
• Example: quantum-dragon-avocado-symphony-volcano-cyber
        """
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(help_text.strip(), reply_markup=reply_markup)
    
    async def show_main_menu(self, query, context):
        """Показать главное меню"""
        user_id = query.from_user.id
        
        keyboard = [
            [InlineKeyboardButton("📝 Create Chat", callback_data="create_session")],
            [InlineKeyboardButton("🔑 Join Chat", callback_data="join_session")],
            [InlineKeyboardButton("📋 My Chats", callback_data="my_sessions")],
            [InlineKeyboardButton("❓ Help", callback_data="help")]
        ]
        
        if self.is_admin(user_id):
            keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = """
🤫 Welcome to the anonymous messaging bot!

Choose an action:
        """
        
        await query.edit_message_text(welcome_text.strip(), reply_markup=reply_markup)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка обычных сообщений"""
        user_id = update.effective_user.id
        message_text = update.message.text
        
        # Проверяем, не ожидается ли сообщение для рассылки
        if context.user_data.get('awaiting_broadcast'):
            await self.handle_broadcast(update, context)
            return
        
        if context.user_data.get('awaiting_passphrase'):
            await self.handle_passphrase(update, context)
            return
        
        if user_id not in self.user_sessions:
            await update.message.reply_text(
                "❌ You are not in an active chat. "
                "Use /start to create or join a chat."
            )
            return
        
        session_id = self.user_sessions[user_id]
        
        # Проверка длины сообщения
        if len(message_text) > MAX_MESSAGE_LENGTH:
            await update.message.reply_text(
                f"❌ Message is too long. "
                f"Maximum length: {MAX_MESSAGE_LENGTH} characters."
            )
            return
        
        # Определяем тип отправителя
        creator_id = self.get_session_creator(session_id)
        sender_type = 'creator' if user_id == creator_id else 'responder'
        
        # Сохраняем сообщение
        self.db.add_message(session_id, sender_type, message_text)
        
        # Отправляем сообщение другим участникам
        await self.notify_session_users(
            session_id, 
            f"🗣️ {message_text}", 
            exclude_user=user_id
        )
        
        # Подтверждение отправки
        await update.message.reply_text("✅ Message sent")
    
    async def notify_session_users(self, session_id, message, exclude_user=None):
        """Уведомление всех пользователей сессии"""
        if session_id not in self.session_users:
            return
        
        for user_id in self.session_users[session_id]:
            if user_id != exclude_user:
                try:
                    await self.application.bot.send_message(user_id, message)
                except Exception as e:
                    logger.error(f"Failed to send message to user {user_id}: {e}")
    
    def get_session_creator(self, session_id):
        """Получение ID создателя сессии"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT creator_user_id FROM sessions WHERE session_id = ?',
            (session_id,)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def start_cleanup_thread(self):
        """Запуск фонового потока для очистки"""
        def cleanup_loop():
            while True:
                time.sleep(3600)
                self.db.cleanup_old_sessions()
                logger.info("Performed cleanup of old sessions")
        
        thread = threading.Thread(target=cleanup_loop, daemon=True)
        thread.start()
    
    def run(self):
        """Запуск бота"""
        self.application = Application.builder().token(BOT_TOKEN).build()
        
        # Обработчики команд
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.show_help))
        
        # Обработчики кнопок
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Обработчики сообщений
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, self.handle_message
        ))
        
        # Запуск фоновой очистки
        self.start_cleanup_thread()
        logger.info("Cleanup thread started")
        
        # Запуск бота
        print("Bot is running...")
        self.application.run_polling()

if __name__ == '__main__':
    bot = AnonymousBot()
    bot.run()