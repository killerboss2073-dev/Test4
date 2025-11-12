#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import logging
import hashlib
import time
import json
import requests
import random
import sqlite3  # Built-in, no need to install
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

print("✅ Python version:", sys.version)
print("✅ SQLite3 version:", sqlite3.version)
print("✅ SQLite3 library version:", sqlite3.sqlite_version)

# ... (ကျန်တဲ့ code အတူတူပါပဲ) ...

# Render environment variables ကနေ token ယူပါ
BOT_TOKEN = os.environ.get('BOT_TOKEN', "8225668512:AAFGuneASode6R-90p9bKg-8GKztEFiUtNs")

# Channel configuration - Auto Signal ချမယ့် Channel
SIGNAL_CHANNEL_USERNAME = "@sakuna_vip"

# Channel configuration - User ဝင်ရမယ့် Channel
CHANNEL_USERNAME = "@Vipsafesingalchannel298"
CHANNEL_LINK = "https://t.me/Vipsafesingalchannel298"

# 777 API endpoint only
API_ENDPOINTS = {
    "777": "https://api.bigwinqaz.com/api/webapi/"
}

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database setup
DB_NAME = "777_auto_bot.db"

# Auto Signal Configuration
AUTO_SIGNAL_ENABLED = True
SIGNAL_INTERVAL = 60  # seconds between signals

# Bet Sequence for Loss (777 platform အတွက်)
BET_SEQUENCE_777 = [10, 30, 70, 160, 320, 760, 1600, 3200, 7600, 16000, 32000, 76000]

# Global storage for tracking current issues
current_issues = {
    '777': {'issue': '', 'bet_type': '', 'amount': 0, 'step': 0}
}

def migrate_database():
    """Migrate database to add missing columns"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(user_settings)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'language' not in columns:
            print("🔧 Migrating database: Adding language column...")
            cursor.execute('ALTER TABLE user_settings ADD COLUMN language TEXT DEFAULT "english"')
            conn.commit()
            print("✅ Database migration completed: language column added")
        
        conn.close()
    except Exception as e:
        print(f"❌ Database migration error: {e}")

def init_database():
    """Initialize SQLite database for 777"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                phone TEXT,
                password TEXT,
                platform TEXT DEFAULT '777',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create user_settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                bet_amount INTEGER DEFAULT 100,
                auto_login BOOLEAN DEFAULT 1,
                platform TEXT DEFAULT '777',
                language TEXT DEFAULT 'english',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create signal_history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signal_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT,
                issue TEXT,
                bet_type TEXT,
                amount INTEGER,
                result TEXT,
                profit_loss INTEGER,
                current_step INTEGER,
                signal_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create bet_sequence table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bet_sequence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT,
                current_step INTEGER DEFAULT 0,
                last_result TEXT,
                total_profit INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("777 Database initialized successfully")
        
    except Exception as e:
        logger.error(f"777 Database initialization error: {e}")

def save_signal_history(platform, issue, bet_type, amount, result, profit_loss, current_step, signal_text):
    """Save signal to history"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO signal_history (platform, issue, bet_type, amount, result, profit_loss, current_step, signal_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (platform, issue, bet_type, amount, result, profit_loss, current_step, signal_text))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error saving signal history: {e}")
        return False

def get_platform_sequence(platform):
    """Get current sequence for platform"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT current_step, last_result, total_profit FROM bet_sequence 
            WHERE platform = ? ORDER BY created_at DESC LIMIT 1
        ''', (platform,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'current_step': result[0],
                'last_result': result[1],
                'total_profit': result[2]
            }
        return {'current_step': 0, 'last_result': None, 'total_profit': 0}
    except Exception as e:
        logger.error(f"Error getting platform sequence: {e}")
        return {'current_step': 0, 'last_result': None, 'total_profit': 0}

def update_platform_sequence(platform, current_step, last_result, total_profit):
    """Update platform sequence"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO bet_sequence (platform, current_step, last_result, total_profit)
            VALUES (?, ?, ?, ?)
        ''', (platform, current_step, last_result, total_profit))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error updating platform sequence: {e}")
        return False

class LotteryBot777:
    def __init__(self, platform='777'):
        self.platform = platform
        self.base_url = API_ENDPOINTS.get(platform, API_ENDPOINTS['777'])
        
        # Set 777 platform headers
        origin = "https://www.bigwinqaz.com"
        referer = "https://www.bigwinqaz.com/"
            
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": origin,
            "Referer": referer,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    def sign_md5(self, data_dict):
        """Generate MD5 signature for API requests"""
        sign_data = data_dict.copy()
        if 'signature' in sign_data:
            del sign_data['signature']
        if 'timestamp' in sign_data:
            del sign_data['timestamp']
        
        sorted_data = dict(sorted(sign_data.items()))
        hash_string = json.dumps(sorted_data, separators=(',', ':')).replace(' ', '')
        
        md5_hash = hashlib.md5(hash_string.encode('utf-8')).hexdigest()
        return md5_hash
    
    def random_key(self):
        """Generate random key for API"""
        xxxx = "xxxxxxxxxxxx4xxxyxxxxxxxxxxxxxxx"
        result = ""
        
        for char in xxxx:
            if char == 'x':
                result += random.choice('0123456789abcdef')
            elif char == 'y':
                result += random.choice('89a')
            else:
                result += char
        return result
    
    async def get_current_issue(self):
        """Get current game issue for 777"""
        try:
            body = {
                "typeId": 1,
                "language": 0,
                "random": self.random_key(),
                "timestamp": int(time.time())
            }
            body["signature"] = self.sign_md5(body).upper()
            
            response = requests.post(
                f"{self.base_url}GetGameIssue",
                headers=self.headers,
                json=body,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('msgCode') == 0:
                    return result.get('data', {}).get('issueNumber', '')
            return ""
        except Exception as e:
            logger.error(f"Get issue error for 777: {e}")
            return ""
    
    async def get_recent_results(self, count=5):
        """Get recent game results for 777"""
        try:
            body = {
                "pageNo": 1,
                "pageSize": count,
                "language": 0,
                "typeId": 1,
                "random": self.random_key(),
                "timestamp": int(time.time())
            }
            body["signature"] = self.sign_md5(body).upper()
            
            response = requests.post(
                f"{self.base_url}GetNoaverageEmerdList",
                headers=self.headers,
                json=body,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('msgCode') == 0:
                    data = result.get('data', {})
                    if data and 'list' in data:
                        return data['list']
            return []
        except Exception as e:
            logger.error(f"Get results error for 777: {e}")
            return []

def analyze_results(results):
    """Analyze recent results and determine next bet"""
    if not results or len(results) < 2:
        return {'bet_type': random.choice(['BIG', 'SMALL']), 'confidence': 'LOW'}
    
    last_result = results[0]
    second_last = results[1]
    
    number = str(last_result.get('number', ''))
    prev_number = str(second_last.get('number', ''))
    
    # Simple pattern analysis
    if number in ['0','1','2','3','4']:
        last_was_small = True
        last_was_big = False
    else:
        last_was_small = False
        last_was_big = True
    
    if prev_number in ['0','1','2','3','4']:
        prev_was_small = True
        prev_was_big = False
    else:
        prev_was_small = False
        prev_was_big = True
    
    # Strategy: Follow the trend if same result twice, otherwise switch
    if last_was_big and prev_was_big:
        return {'bet_type': 'BIG', 'confidence': 'HIGH'}
    elif last_was_small and prev_was_small:
        return {'bet_type': 'SMALL', 'confidence': 'HIGH'}
    elif last_was_big and prev_was_small:
        return {'bet_type': 'SMALL', 'confidence': 'MEDIUM'}
    else:  # last_was_small and prev_was_big
        return {'bet_type': 'BIG', 'confidence': 'MEDIUM'}

def calculate_profit_loss(bet_type, result_number, bet_amount):
    """Calculate profit/loss for a bet"""
    result_number = str(result_number)
    
    if bet_type == 'BIG':
        if result_number in ['5','6','7','8','9']:
            # Win - 96% payout
            profit = int(bet_amount * 0.96)
            return 'WIN', profit
        else:
            # Loss
            return 'LOSS', -bet_amount
    elif bet_type == 'SMALL':
        if result_number in ['0','1','2','3','4']:
            # Win - 96% payout
            profit = int(bet_amount * 0.96)
            return 'WIN', profit
        else:
            # Loss
            return 'LOSS', -bet_amount
    else:
        return 'UNKNOWN', 0

def get_next_bet_amount_777(current_step):
    """Get bet amount based on current step in sequence for 777"""
    if current_step < len(BET_SEQUENCE_777):
        return BET_SEQUENCE_777[current_step] * 100
    else:
        return BET_SEQUENCE_777[-1] * 100

def generate_signal_text_777(issue, bet_type, amount, current_step, total_profit, confidence):
    """Generate signal message for channel - 777 Only"""
    
    signal_text = f"""
🎰 **777 VIP SIGNAL** 🎯

⌛️ Issue: `{issue}`
🎲 Bet Type: **{bet_type}**
💰 Amount: **{amount:,} K**
📈 Step: **{current_step + 1}**
🏆 Total Profit: **{total_profit:,} K**

🔮 Confidence: **{confidence}**
⚡ Platform: **777 LOTTERY**
    """
    
    return signal_text

def generate_instant_result_text_777(issue, bet_type, amount, result, profit_loss, current_step, total_profit, result_number):
    """777 အတွက် ချက်ချင်း result ပြမယ့် message"""
    
    if result == 'WIN':
        emoji = "🟢"
        result_text = "WIN ✅"
        details = f"💰 Win Amount: **+{profit_loss:,} K**"
        next_action = "🔄 **Next Bet:** Back to Step 1"
    else:
        emoji = "🔴" 
        result_text = "LOSS ❌"
        details = f"💸 Loss Amount: **{amount:,} K**"
        next_step = current_step + 1
        next_amount = get_next_bet_amount_777(next_step)
        next_action = f"📈 **Next Bet:** Step {next_step + 1} ({next_amount:,} K)"
    
    instant_message = f"""
{emoji} **777 RESULT - {result_text}**

🎯 Issue: `{issue}`
🎲 Bet: {bet_type}
🎯 Result: {result_number} - {result}
{details}

📊 Current Step: {current_step + 1}
💰 Total Profit: **{total_profit:,} K**

{next_action}

⚡ Platform: **777 LOTTERY**
    """
    
    return instant_message

async def send_signal_for_777(context: ContextTypes.DEFAULT_TYPE):
    """Send signal and check result for 777 platform"""
    try:
        bot = LotteryBot777('777')
        
        # Get current issue and recent results
        current_issue = await bot.get_current_issue()
        recent_results = await bot.get_recent_results(3)
        
        if not current_issue:
            logger.error("No current issue for 777")
            return False
        
        if not recent_results:
            logger.error("No recent results for 777")
            return False
        
        # Get current sequence for platform
        sequence_data = get_platform_sequence('777')
        current_step = sequence_data['current_step']
        total_profit = sequence_data['total_profit']
        
        # Analyze results to determine next bet
        analysis = analyze_results(recent_results)
        bet_type = analysis['bet_type']
        confidence = analysis['confidence']
        
        # Get bet amount based on current step
        bet_amount = get_next_bet_amount_777(current_step)
        
        # Store current issue data
        current_issues['777'] = {
            'issue': current_issue,
            'bet_type': bet_type,
            'amount': bet_amount,
            'step': current_step
        }
        
        # Generate and send signal
        signal_text = generate_signal_text_777(current_issue, bet_type, bet_amount, current_step, total_profit, confidence)
        
        # Send signal to channel
        await context.bot.send_message(
            chat_id=SIGNAL_CHANNEL_USERNAME,
            text=signal_text,
            parse_mode='Markdown'
        )
        
        logger.info(f"777 Signal sent: {bet_type} {bet_amount}K (Step {current_step + 1})")
        return True
        
    except Exception as e:
        logger.error(f"Error sending signal for 777: {e}")
        return False

async def check_777_results_continuously(context: ContextTypes.DEFAULT_TYPE):
    """777 platform အတွက် ချက်ချင်း result စစ်ဆေးခြင်း"""
    try:
        platform = '777'
        logger.info("Starting continuous result checking for 777")
        
        while True:
            try:
                # လက်ရှိ issue ရှိမှသာ result စစ်မယ်
                current_issue_data = current_issues[platform]
                if current_issue_data['issue']:
                    bot = LotteryBot777(platform)
                    
                    # လတ်တလော result 2 ခုယူမယ်
                    new_results = await bot.get_recent_results(2)
                    if new_results and len(new_results) > 0:
                        latest_result = new_results[0]
                        result_issue = latest_result.get('issueNumber', '')
                        result_number = str(latest_result.get('number', ''))
                        
                        # လက်ရှိ issue နဲ့ match ဖြစ်ရင် result စစ်မယ်
                        if result_issue == current_issue_data['issue']:
                            await process_777_result(context, platform, current_issue_data, result_issue, result_number)
                    
                    # မတူရင် နောက်တစ်ခုစစ်မယ်
                    elif len(new_results) > 1:
                        second_result = new_results[1]
                        result_issue = second_result.get('issueNumber', '')
                        result_number = str(second_result.get('number', ''))
                        
                        if result_issue == current_issue_data['issue']:
                            await process_777_result(context, platform, current_issue_data, result_issue, result_number)
                
                # 3 seconds တစ်ခါ check မယ်
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.error(f"Error in continuous 777 result check: {e}")
                await asyncio.sleep(5)
                
    except Exception as e:
        logger.error(f"Continuous 777 result checking stopped: {e}")

async def process_777_result(context: ContextTypes.DEFAULT_TYPE, platform: str, issue_data: dict, result_issue: str, result_number: str):
    """777 result ကို process လုပ်ခြင်း"""
    try:
        current_issue = issue_data['issue']
        bet_type = issue_data['bet_type']
        bet_amount = issue_data['amount']
        current_step = issue_data['step']
        
        # Get current sequence
        sequence_data = get_platform_sequence(platform)
        total_profit = sequence_data['total_profit']
        
        # Calculate result
        result, profit_loss = calculate_profit_loss(bet_type, result_number, bet_amount)
        
        # Update sequence and total profit
        if result == 'WIN':
            new_step = 0  # Reset to step 1
            new_total_profit = total_profit + profit_loss
        else:  # LOSS
            new_step = current_step + 1
            if new_step >= len(BET_SEQUENCE_777):
                new_step = len(BET_SEQUENCE_777) - 1
            new_total_profit = total_profit + profit_loss
        
        # Update platform sequence
        update_platform_sequence(platform, new_step, result, new_total_profit)
        
        # Generate result message
        result_text = generate_instant_result_text_777(
            current_issue, bet_type, bet_amount, result, 
            profit_loss, current_step, new_total_profit, result_number
        )
        
        # Send result to channel
        await context.bot.send_message(
            chat_id=SIGNAL_CHANNEL_USERNAME,
            text=result_text,
            parse_mode='Markdown'
        )
        
        # Save to history
        save_signal_history(
            platform, current_issue, bet_type, bet_amount, result, 
            profit_loss, current_step, result_text
        )
        
        # Clear current issue after processing result
        current_issues[platform] = {'issue': '', 'bet_type': '', 'amount': 0, 'step': 0}
        
        logger.info(f"777 Result processed: {result} (Profit: {profit_loss}, New Step: {new_step})")
        
        # WinLoss ပြပြီးရင် နောက် Issue ထိုးဖို့ signal
        await asyncio.sleep(2)
        await send_signal_for_777(context)
        
        return True
        
    except Exception as e:
        logger.error(f"Error processing 777 result: {e}")
        return False

async def start_auto_signal_777(context: ContextTypes.DEFAULT_TYPE):
    """Start auto signal service for 777 platform only"""
    try:
        logger.info("777 Auto signal service started")
        
        # Initial delay to let bot fully start
        await asyncio.sleep(10)
        
        # 777 platform အတွက် continuous result checking စမယ်
        asyncio.create_task(check_777_results_continuously(context))
        logger.info("777 continuous result checking started")
        
        # ပထမဆုံး signal ကိုချက်ချင်းပို့မယ်
        await send_signal_for_777(context)
        
        while True:
            try:
                start_time = datetime.now()
                logger.info(f"Starting new 777 signal cycle at {start_time.strftime('%H:%M:%S')}")
                
                # လက်ရှိ issue မရှိမှသာ signal ပို့မယ်
                current_issue_data = current_issues['777']
                if not current_issue_data['issue']:
                    signal_sent = await send_signal_for_777(context)
                    
                    if signal_sent:
                        logger.info("777 signal sent successfully")
                    else:
                        logger.error("Failed to send 777 signal")
                
                # Calculate time until next cycle
                cycle_duration = (datetime.now() - start_time).total_seconds()
                wait_time = max(0, SIGNAL_INTERVAL - cycle_duration)
                
                if wait_time > 0:
                    logger.info(f"Waiting {wait_time:.1f} seconds for next 777 signal")
                    await asyncio.sleep(wait_time)
                else:
                    logger.info("Starting next 777 signal immediately")
                    
            except Exception as e:
                logger.error(f"Error in 777 signal cycle: {e}")
                await asyncio.sleep(10)
                
    except Exception as e:
        logger.error(f"777 Auto signal service stopped: {e}")

def get_join_channel_keyboard():
    """Get keyboard for joining channel"""
    keyboard = [
        [InlineKeyboardButton("📢 Join Our Channel", url=CHANNEL_LINK)],
        [InlineKeyboardButton("✅ I've Joined", callback_data="check_join")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def check_channel_membership(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Check if user is a member of the channel"""
    try:
        chat_member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        
        if chat_member.status in ['member', 'administrator', 'creator']:
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"Error checking channel membership: {e}")
        return True

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline keyboards"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    if query.data == "check_join":
        has_joined = await check_channel_membership(update, context, query.from_user.id)
        
        if has_joined:
            await query.edit_message_text(
                "✅ Thank you for joining our channel! You can now use the bot.\n\n"
                "Press /start to begin.",
                reply_markup=None
            )
        else:
            await query.edit_message_text(
                "❌ You haven't joined our channel yet. Please join the channel first to use the bot.",
                reply_markup=get_join_channel_keyboard()
            )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    user_id = str(user.id)
    
    has_joined = await check_channel_membership(update, context, user.id)
    
    if not has_joined:
        welcome_text = f"""
🎰 **Welcome to 777 Auto Signal Bot** 🎯

Dear {user.first_name},

To use this bot, you need to join our official channel first for VIP signals.

**Why join our channel?**
• 📊 Get real-time 777 LOTTERY signals
• 💡 Professional analysis  
• 🔔 Instant result updates
• 🎯 High accuracy predictions

Please join our channel below and then click **✅ I've Joined** to verify.
        """
        await update.message.reply_text(
            welcome_text,
            reply_markup=get_join_channel_keyboard(),
            parse_mode='Markdown'
        )
        return
    
    welcome_text = f"""
🎰 **777 Auto Signal Bot** 🎯

Welcome {user.first_name}!

🤖 **777 Automatic Signal Features:**
• 📊 777 LOTTERY Signals Only
• ⏰ Instant WinLoss + Next Issue
• 📈 Real Win/Loss Results
• 🔢 Smart Bet Sequence
• 🎲 BIG/SMALL Only Strategy
• ⚡ Instant Result Checking

📢 **Channel:** @Vipsafesingalchannel298

🚀 **Current Mode:** 777 platform signals with instant WinLoss and immediate next issue!
        """
    await update.message.reply_text(welcome_text, parse_mode='Markdown')
    
    # Start auto signal service if not already running
    if 'auto_signal_started' not in context.bot_data:
        context.bot_data['auto_signal_started'] = True
        asyncio.create_task(start_auto_signal_777(context))
        logger.info("777 Auto signal service started")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check current status for 777 platform"""
    try:
        platform = '777'
        sequence_data = get_platform_sequence(platform)
        current_step = sequence_data['current_step']
        total_profit = sequence_data['total_profit']
        last_result = sequence_data['last_result'] or 'N/A'
        
        current_issue = current_issues[platform]['issue']
        current_bet = current_issues[platform]['bet_type']
        
        status_text = f"""
📊 **777 LOTTERY Bot Status**

🎯 Current Step: {current_step + 1}
📈 Last Result: {last_result}
💰 Total Profit: {total_profit:,} K
        """
        
        if current_issue:
            status_text += f"""
📋 Current Issue: {current_issue}
🎲 Current Bet: {current_bet}
            """
        
        status_text += f"""
⏰ Signal Mode: Instant WinLoss + Next Issue
🔢 Bet Sequence: {', '.join(map(str, BET_SEQUENCE_777))}
⚡ Result Mode: Continuous Checking
🕒 Last Update: {datetime.now().strftime('%H:%M:%S')}
        """
        
        await update.message.reply_text(status_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in status command: {e}")
        await update.message.reply_text("❌ Error getting status.")

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset 777 platform to step 1"""
    try:
        platform = '777'
        
        update_platform_sequence(platform, 0, 'RESET', 0)
        current_issues[platform] = {'issue': '', 'bet_type': '', 'amount': 0, 'step': 0}
        
        await update.message.reply_text(
            "✅ **777 Platform reset to Step 1!**\n\n"
            "Sequence has been reset and total profit cleared.",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in reset command: {e}")
        await update.message.reply_text("❌ Error resetting platform.")

async def force_signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force send signal for 777 platform immediately"""
    try:
        await update.message.reply_text("🔄 Forcing immediate 777 signal...")
        
        success = await send_signal_for_777(context)
        
        if success:
            await update.message.reply_text("✅ 777 signal sent successfully!")
        else:
            await update.message.reply_text("❌ Failed to send 777 signal.")
        
    except Exception as e:
        logger.error(f"Error in force signal command: {e}")
        await update.message.reply_text("❌ Error sending signal.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    user_id = str(update.effective_user.id)
    text = update.message.text
    
    if text == "📊 Status":
        await status_command(update, context)
    elif text == "🔄 Reset":
        await reset_command(update, context)
    elif text == "🚀 Force Signal":
        await force_signal_command(update, context)
    else:
        await update.message.reply_text(
            "Please use /start to begin or check the status with 📊 Status",
            parse_mode='Markdown'
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Exception while handling an update: {context.error}")
    
    if update and update.message:
        await update.message.reply_text(
            "❌ An error occurred. Please try again later.",
            parse_mode='Markdown'
        )

def main():
    # Bot Token စစ်ဆေးခြင်း
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Please set your BOT_TOKEN in environment variables!")
        return
    
    # Render compatibility
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 Starting 777 Auto Signal Bot on port {port}")
    
    init_database()
    migrate_database()
    
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("status", status_command))
        application.add_handler(CommandHandler("reset", reset_command))
        application.add_handler(CommandHandler("force", force_signal_command))
        application.add_handler(CallbackQueryHandler(handle_callback_query))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_error_handler(error_handler)
        
        logger.info("777 Auto Signal Bot starting...")
        print("🤖 777 Auto Signal Bot is running...")
        print("📢 Auto Signal System: ENABLED")
        print(f"📊 Signal Channel: {SIGNAL_CHANNEL_USERNAME}")
        print("🎯 Platform: 777 LOTTERY ONLY")
        print("🎲 Bet Type: BIG/SMALL Only")
        print(f"🔢 Bet Sequence: {', '.join(map(str, BET_SEQUENCE_777))}")
        print("⚡ Result Mode: INSTANT WINLOSS + NEXT ISSUE")
        print("🔄 Win Strategy: Reset to Step 1")
        print("📈 Loss Strategy: Progress through sequence")
        print("💰 Real Profit/Loss Tracking")
        print("⏹️  Press Ctrl+C to stop.")
        
        # Start polling
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"❌ Bot startup failed: {e}")

if __name__ == "__main__":
    main()
