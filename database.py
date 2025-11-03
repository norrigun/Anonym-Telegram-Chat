import sqlite3
import json
import time
from datetime import datetime, timedelta
import secrets
import hashlib

class AnonymousDatabase:
    def __init__(self, db_path='anonymous_messages.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица сессий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                passphrase_hash TEXT NOT NULL,
                creator_user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # Таблица сообщений
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                sender_type TEXT NOT NULL, -- 'creator' или 'responder'
                message_text TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def generate_passphrase(self):
        """Генерация уникальной ключ-фразы на английском"""
        words = [
            # Colors
            'amber', 'azure', 'bronze', 'crimson', 'emerald', 'golden', 'ivory', 'jade', 
            'lavender', 'magenta', 'obsidian', 'pearl', 'quartz', 'ruby', 'sapphire', 'topaz',
            
            # Animals
            'alligator', 'butterfly', 'cheetah', 'dolphin', 'elephant', 'flamingo', 'giraffe', 
            'hummingbird', 'iguana', 'jaguar', 'koala', 'leopard', 'mongoose', 'narwhal', 'octopus',
            'penguin', 'quetzal', 'raccoon', 'salamander', 'tiger', 'unicorn', 'vulture', 'wolf',
            
            # Nature
            'asteroid', 'blizzard', 'cascade', 'diamond', 'echo', 'forest', 'galaxy', 'horizon',
            'infinity', 'jungle', 'kingdom', 'lagoon', 'mountain', 'nebula', 'ocean', 'pyramid',
            'quantum', 'river', 'sunset', 'tundra', 'universe', 'volcano', 'waterfall', 'zenith',
            
            # Technology
            'algorithm', 'blockchain', 'cyber', 'digital', 'encryption', 'firewall', 'graphics',
            'hologram', 'internet', 'javascript', 'kernel', 'linux', 'matrix', 'network', 'opensource',
            'python', 'quantum', 'robotics', 'server', 'terminal', 'ubuntu', 'virtual', 'wireless',
            
            # Fantasy/Mythical
            'arcanum', 'banshee', 'centaur', 'dragon', 'elf', 'phoenix', 'griffin', 'hydra',
            'illusion', 'jinn', 'kraken', 'leviathan', 'mermaid', 'necromancer', 'oracle', 'pegasus',
            'quest', 'rune', 'sorcerer', 'titan', 'unicorn', 'valkyrie', 'wizard', 'yeti',
            
            # Science
            'atom', 'biology', 'chemistry', 'dimension', 'energy', 'fusion', 'gravity', 'hypothesis',
            'isotope', 'joule', 'kinetic', 'laboratory', 'molecule', 'neutron', 'orbit', 'particle',
            'quantum', 'research', 'spectrum', 'theory', 'ultraviolet', 'velocity', 'wavelength',
            
            # Food
            'avocado', 'blueberry', 'chocolate', 'dragonfruit', 'elderberry', 'fig', 'guava',
            'honeydew', 'icecream', 'jackfruit', 'kiwi', 'lychee', 'mango', 'nectarine', 'olive',
            'pomegranate', 'quince', 'raspberry', 'strawberry', 'tangerine', 'ugli', 'vanilla',
            
            # Music
            'acoustic', 'ballad', 'concert', 'digital', 'electric', 'fugue', 'guitar', 'harmony',
            'instrument', 'jazz', 'keyboard', 'lyrics', 'melody', 'note', 'opera', 'piano',
            'quartet', 'rhythm', 'symphony', 'tempo', 'ukulele', 'violin', 'waltz',
            
            # Travel
            'adventure', 'backpack', 'cruise', 'destination', 'expedition', 'frontier', 'globe',
            'horizon', 'island', 'journey', 'kingdom', 'landmark', 'map', 'navigation', 'odyssey',
            'passport', 'quest', 'route', 'safari', 'tourism', 'voyage', 'wanderlust'
        ]
        
        while True:
            # Генерируем фразу из 6 слов для большей безопасности
            passphrase = '-'.join(secrets.choice(words) for _ in range(6))
            passphrase_hash = self._hash_passphrase(passphrase)
            
            if not self._passphrase_exists(passphrase_hash):
                return passphrase
    
    def _hash_passphrase(self, passphrase):
        """Хеширование ключ-фразы"""
        return hashlib.sha256(passphrase.encode()).hexdigest()
    
    def _passphrase_exists(self, passphrase_hash):
        """Проверка существования ключ-фразы"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT 1 FROM sessions WHERE passphrase_hash = ? AND is_active = TRUE',
            (passphrase_hash,)
        )
        
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
    
    def create_session(self, creator_user_id):
        """Создание новой сессии"""
        session_id = secrets.token_hex(16)
        passphrase = self.generate_passphrase()
        passphrase_hash = self._hash_passphrase(passphrase)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO sessions (session_id, passphrase_hash, creator_user_id)
            VALUES (?, ?, ?)
        ''', (session_id, passphrase_hash, creator_user_id))
        
        conn.commit()
        conn.close()
        
        return session_id, passphrase
    
    def join_session(self, passphrase, responder_user_id):
        """Присоединение к сессии по ключ-фразе"""
        passphrase_hash = self._hash_passphrase(passphrase)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT session_id FROM sessions 
            WHERE passphrase_hash = ? AND is_active = TRUE
        ''', (passphrase_hash,))
        
        result = cursor.fetchone()
        
        if result:
            session_id = result[0]
            # Обновляем время последней активности
            cursor.execute('''
                UPDATE sessions SET last_activity = CURRENT_TIMESTAMP 
                WHERE session_id = ?
            ''', (session_id,))
            conn.commit()
            conn.close()
            return session_id
        
        conn.close()
        return None
    
    def add_message(self, session_id, sender_type, message_text):
        """Добавление сообщения в сессию"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO messages (session_id, sender_type, message_text)
            VALUES (?, ?, ?)
        ''', (session_id, sender_type, message_text))
        
        # Обновляем время последней активности сессии
        cursor.execute('''
            UPDATE sessions SET last_activity = CURRENT_TIMESTAMP 
            WHERE session_id = ?
        ''', (session_id,))
        
        conn.commit()
        conn.close()
    
    def get_session_messages(self, session_id):
        """Получение всех сообщений сессии"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT message_text, sender_type, timestamp 
            FROM messages 
            WHERE session_id = ? 
            ORDER BY timestamp ASC
        ''', (session_id,))
        
        messages = cursor.fetchall()
        conn.close()
        return messages
    
    def get_user_active_sessions(self, user_id):
        """Получение активных сессий пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT session_id FROM sessions 
            WHERE (creator_user_id = ? OR session_id IN (
                SELECT DISTINCT m.session_id FROM messages m
                JOIN sessions s ON m.session_id = s.session_id
                WHERE s.creator_user_id != ? AND s.is_active = TRUE
            )) AND is_active = TRUE
        ''', (user_id, user_id))
        
        sessions = [row[0] for row in cursor.fetchall()]
        conn.close()
        return sessions
    
    def cleanup_old_sessions(self):
        """Очистка старых сессий"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        cursor.execute('''
            UPDATE sessions SET is_active = FALSE 
            WHERE last_activity < ? AND is_active = TRUE
        ''', (cutoff_time,))
        
        conn.commit()
        conn.close()
    
    def close_session(self, session_id):
        """Закрытие сессии"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE sessions SET is_active = FALSE WHERE session_id = ?
        ''', (session_id,))
        
        conn.commit()
        conn.close()

    # Новые методы для статистики
    def get_system_stats(self):
        """Получение статистики системы"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Общее количество активных сессий
        cursor.execute('SELECT COUNT(*) FROM sessions WHERE is_active = TRUE')
        total_sessions = cursor.fetchone()[0] or 0
        
        # Общее количество сообщений
        cursor.execute('SELECT COUNT(*) FROM messages')
        total_messages = cursor.fetchone()[0] or 0
        
        # Старые сессии (24+ часов)
        cutoff_time = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('SELECT COUNT(*) FROM sessions WHERE last_activity < ? AND is_active = TRUE', (cutoff_time,))
        old_sessions_result = cursor.fetchone()
        old_sessions = old_sessions_result[0] if old_sessions_result else 0
        
        # Сессии созданные сегодня
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('SELECT COUNT(*) FROM sessions WHERE DATE(created_at) = ?', (today,))
        sessions_today_result = cursor.fetchone()
        sessions_today = sessions_today_result[0] if sessions_today_result else 0
        
        # Сообщения сегодня
        cursor.execute('SELECT COUNT(*) FROM messages WHERE DATE(timestamp) = ?', (today,))
        messages_today_result = cursor.fetchone()
        messages_today = messages_today_result[0] if messages_today_result else 0
        
        # Среднее количество сообщений на сессию
        avg_messages = total_messages / total_sessions if total_sessions > 0 else 0
        
        # Уникальные пользователи (создатели сессий)
        cursor.execute('SELECT COUNT(DISTINCT creator_user_id) FROM sessions WHERE is_active = TRUE')
        unique_users_result = cursor.fetchone()
        unique_users = unique_users_result[0] if unique_users_result else 0
        
        conn.close()
        
        return {
            'total_sessions': total_sessions,
            'total_messages': total_messages,
            'old_sessions': old_sessions,
            'sessions_today': sessions_today,
            'messages_today': messages_today,
            'avg_messages_per_session': round(avg_messages, 2),
            'unique_users': unique_users
        }
    
    def get_all_active_sessions_with_stats(self):
        """Получение всех активных сессий со статистикой"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT s.session_id, 
                   s.creator_user_id,
                   s.created_at,
                   s.last_activity,
                   COUNT(m.message_id) as message_count
            FROM sessions s
            LEFT JOIN messages m ON s.session_id = m.session_id
            WHERE s.is_active = TRUE
            GROUP BY s.session_id
            ORDER BY s.last_activity DESC
        ''')
        
        sessions = cursor.fetchall()
        conn.close()
        return sessions
    
    def get_all_active_session_ids(self):
        """Получение ID всех активных сессий"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT session_id FROM sessions WHERE is_active = TRUE')
        sessions = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return sessions