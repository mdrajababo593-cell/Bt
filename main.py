import os
import sys
import ssl
import json
import time
import random
import asyncio
from datetime import datetime
import aiohttp

# ========== 1. CRITICAL TIMEZONE PATCH ==========
import pytz
try:
    import tzlocal
    tzlocal.get_localzone = lambda: pytz.UTC
    tzlocal.get_localzone_name = lambda: "UTC"
except Exception:
    pass

try:
    import apscheduler.util
    def _safe_astimezone(tz):
        if tz is None:
            return pytz.UTC
        if isinstance(tz, str):
            try:
                return pytz.timezone(tz)
            except Exception:
                return pytz.UTC
        if hasattr(tz, 'localize') and hasattr(tz, 'normalize'):
            return tz
        return pytz.UTC
    apscheduler.util.astimezone = _safe_astimezone
except Exception:
    pass

# ========== 2. CRYPTO & TELEGRAM IMPORTS ==========
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from protobuf_decoder.protobuf_decoder import Parser

# Protobuf & Local Modules
from xPARA import *
from xHeaders import *
from Pb2 import MajoRLoGinrEs_pb2, PorTs_pb2, MajoRLoGinrEq_pb2

# ========== COLOR CODES FOR TERMINAL ==========
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_MAGENTA = "\033[95m"
C_WHITE = "\033[97m"
C_RESET = "\033[0m"
BOLD = "\033[1m"

# ========== CONFIGURATION ==========
TELEGRAM_TOKEN = "8038891325:AAFNfusJm-Zkcn6joDHt6442rMJEJsRJ5u8"

# এখানে আপনার ও অন্য এডমিনদের টেলিগ্রাম নিউমেরিক আইডি দিন
ADMIN_IDS = [6805684286] 

login_url, ob, version = "https://loginbp.ggpolarbear.com/", "OB54", "1.130.22"
TIMEOUT = aiohttp.ClientTimeout(total=15)

# সর্বোচ্চ ফিক্সড সেশন সময়সীমা (কঠোরভাবে ৫ মিনিট)
MAX_SESSION_MINUTES = 5

# প্রতি ৪ ঘন্টা পর পর অটো-রিস্টার্ট (সেকেন্ডে)
AUTO_RESTART_INTERVAL = 4 * 60 * 60  # 4 Hours

# গ্লোবাল ডাটাবেজ ও ক্লায়েন্ট পুল
connected_clients_bd = {}
connected_clients_ind = {}
active_spam_tasks = {}             # target_uid -> asyncio.Task

# রাউন্ড-রবিন লোড ব্যালেন্সার
bd_rr_idx = 0
ind_rr_idx = 0
rr_lock = asyncio.Lock()

# অ্যানিমেশন ফ্রেমসমূহ
SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
FIRE_FRAMES = ["🔥", "⚡", "💥", "✨", "🌀", "🚀"]

# ---------- ADMIN KEYBOARD GENERATOR ----------
def get_admin_keyboard():
    keyboard = [
        [KeyboardButton("🔄 Restart Engine"), KeyboardButton("📊 Server Status")],
        [KeyboardButton("🛑 Stop All Attacks"), KeyboardButton("❓ Help / Commands")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ---------- UI & ANIMATION GENERATORS ----------
def generate_progress_bar(percentage, length=16):
    filled = int(length * (percentage / 100))
    bar = "▰" * filled + "▱" * (length - filled)
    return f"[{bar}] {percentage:.1f}%"

def generate_live_spam_box(uid, room_id, server, elapsed_sec, total_sec, packets_sent, frame_idx, user_name="User"):
    percentage = min(100.0, (elapsed_sec / total_sec) * 100)
    prog_bar = generate_progress_bar(percentage, length=16)
    spinner = SPINNER_FRAMES[frame_idx % len(SPINNER_FRAMES)]
    fire = FIRE_FRAMES[frame_idx % len(FIRE_FRAMES)]
    
    rem_sec = max(0, total_sec - elapsed_sec)
    time_str = f"{elapsed_sec//60:02d}:{elapsed_sec%60:02d} / {total_sec//60:02d}:{total_sec%60:02d}"
    rem_str = f"{rem_sec//60:02d}m {rem_sec%60:02d}s"
    
    box =  "╔═══════════════════════════════════════════════════════════════════╗\n"
    box += f"║       {fire} ARIYAN CYBER SPAM ENGINE - RUNNING {spinner} {fire}        ║\n"
    box += "╠═══════════════════════════════════════════════════════════════════╣\n"
    box += f"  👤 Requested By        :: @{user_name}\n"
    box += f"  🎯 Target Player UID   :: {uid}\n"
    box += f"  🏠 Active Custom Room  :: {room_id}\n"
    box += f"  🌐 Routed Server       :: {server.upper()} REGION\n"
    box += f"  ⚡ Transmission Speed  :: ~25 Packets / Sec (Burst Mode)\n"
    box += f"  📦 Packets Delivered   :: {packets_sent:,} Packets\n"
    box += f"  ⏱️ Time Elapsed/Total  :: {time_str} ({rem_str} left)\n"
    box += f"  🔒 Max Session Cap     :: Strictly {MAX_SESSION_MINUTES} Minutes\n"
    box += "╠═══════════════════════════════════════════════════════════════════╣\n"
    box += f"  🚀 PROGRESS {spinner}       :: {prog_bar}\n"
    box += "╠═══════════════════════════════════════════════════════════════════╣\n"
    box += "║  🛑 বন্ধ করতে লিখুন: /stop " + str(uid).ljust(35) + " ║\n"
    box += "╚═══════════════════════════════════════════════════════════════════╝"
    return f"```\n{box}\n```"

def generate_completed_spam_box(uid, room_id, server, total_packets, duration_mins, user_name="User"):
    box =  "╔═══════════════════════════════════════════════════════════════════╗\n"
    box += "║              ✅ SPAM OPERATION COMPLETED SUCCESSFULLY ✅          ║\n"
    box += "╠═══════════════════════════════════════════════════════════════════╣\n"
    box += f"  👤 Requested By      :: @{user_name}\n"
    box += f"  🎯 Target UID        :: {uid}\n"
    box += f"  🏠 Target Room ID    :: {room_id}\n"
    box += f"  🌐 Server Region     :: {server.upper()}\n"
    box += f"  ⏱️ Total Run Time    :: {duration_mins} Minutes (Max Session Done)\n"
    box += f"  📦 Total Delivered   :: {total_packets:,} Flooded Packets\n"
    box += f"  📊 Final Status      :: [▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰] 100.0% DONE\n"
    box += "╠═══════════════════════════════════════════════════════════════════╣\n"
    box += "║                 👑 POWERED BY WINTER ARIYAN 👑                    ║\n"
    box += "╚═══════════════════════════════════════════════════════════════════╝"
    return f"```\n{box}\n```"

def boxed(text, title="ARIYAN BOT"):
    lines = text.split('\n')
    max_len = max(len(line) for line in lines) + 4
    border = "╔" + "═" * (max_len - 2) + "╗"
    mid = f"║ {title.center(max_len - 4)} ║"
    sep = "╠" + "═" * (max_len - 2) + "╣"
    footer = "╚" + "═" * (max_len - 2) + "╝"
    content = "\n".join(f"║ {line.ljust(max_len - 4)} ║" for line in lines)
    return f"```\n{border}\n{mid}\n{sep}\n{content}\n{footer}\n```"

# ---------- PROTOCOL HELPERS & HEADERS ----------
Hr_Login = {
    "User-Agent": "fadai/1.0 (Linux; Android 13; SM-S918B Build/TP1A.220.624.014)",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Unity-Version": "2018.4.11f1",
    "X-GA": "v1 1",
    "ReleaseVersion": "OB54"
}

def get_random_color():
    colors = ["[FF0000]", "[00FF00]", "[0000FF]", "[FFFF00]", "[FF00FF]", "[00FFFF]", "[FFFFFF]", "[FFA500]", "[FFC0CB]", "[FFD700]"]
    return random.choice(colors)

async def EnC_Vr(N):
    if N < 0: return b''
    H = []
    while True:
        RedZed = N & 0x7F
        N >>= 7
        if N: RedZed |= 0x80
        H.append(RedZed)
        if not N: break
    return bytes(H)

async def CrEaTe_VarianT(fn, val):
    return await EnC_Vr((fn << 3) | 0) + await EnC_Vr(val)

async def CrEaTe_LenGTh(fn, val):
    ev = val.encode() if isinstance(val, str) else val
    return await EnC_Vr((fn << 3) | 2) + await EnC_Vr(len(ev)) + ev

async def CrEaTe_ProTo(fields):
    packet = bytearray()
    for f, v in fields.items():
        if isinstance(v, dict):
            nested = await CrEaTe_ProTo(v)
            packet.extend(await CrEaTe_LenGTh(f, nested))
        elif isinstance(v, int):
            packet.extend(await CrEaTe_VarianT(f, v))
        elif isinstance(v, (str, bytes)):
            packet.extend(await CrEaTe_LenGTh(f, v))
    return bytes(packet)

async def DecodE_HeX(H):
    F = str(hex(H))[2:]
    return "0" + F if len(F) == 1 else F

async def EnC_PacKeT(HeX, K, V):
    cipher = AES.new(K, AES.MODE_CBC, V)
    return cipher.encrypt(pad(bytes.fromhex(HeX), 16)).hex()

async def GeneRaTePk(Pk, N, K, V):
    PkEnc = await EnC_PacKeT(Pk, K, V)
    _ = await DecodE_HeX(len(PkEnc) // 2)
    HeadEr = N + "000000" if len(_) == 2 else N + "00000" if len(_) == 3 else N + "0000" if len(_) == 4 else N + "000"
    return bytes.fromhex(HeadEr + _ + PkEnc)

# ---------- STATUS DECODER ENGINE ----------
async def _vr(n):
    h = []
    while True:
        b = n & 0x7F; n >>= 7
        if n: b |= 0x80
        h.append(b)
        if not n: break
    return bytes(h)

async def _enc(hx, k, v):
    return AES.new(k, AES.MODE_CBC, v).encrypt(pad(bytes.fromhex(hx), 16)).hex()

async def _hx(n):
    f = hex(n)[2:]
    return ('0' + f) if len(f) == 1 else f

async def _var(fn, val):
    return await _vr((fn << 3) | 0) + await _vr(val)

async def _len(fn, val):
    e = val.encode() if isinstance(val, str) else val
    return await _vr((fn << 3) | 2) + await _vr(len(e)) + e

async def _pb(flds):
    p = bytearray()
    for f, v in flds.items():
        if isinstance(v, dict): p.extend(await _len(f, await _pb(v)))
        elif isinstance(v, int): p.extend(await _var(f, v))
        elif isinstance(v, (str, bytes)): p.extend(await _len(f, v))
    return p

async def _pk(px, n, k, v):
    e = await _enc(px, k, v)
    _ = await _hx(len(e) // 2)
    m = {2: '000000', 3: '00000', 4: '000', 5: '00'}
    length_prefix = m.get(len(_), '0000')
    return bytes.fromhex(n + length_prefix + _ + e)

async def _fix(rs):
    d = {}
    for r in rs:
        fd = {'wire_type': r.wire_type}
        if r.wire_type in ('varint', 'string', 'bytes'): fd['data'] = r.data
        elif r.wire_type == 'length_delimited': fd['data'] = await _fix(r.data.results)
        d[r.field] = fd
    return d

async def _parse(hx):
    try: return json.dumps(await _fix(Parser().parse(hx)))
    except Exception: return None

async def _uidEnc(uid):
    return (await _pb({1: int(uid)})).hex()[2:]

async def _stPkt(uid, k, v):
    ue = await _uidEnc(int(uid))
    return await _pk(f"080112090A05{ue}1005", '0F15', k, v)

async def _rmPkt(ruid, k, v):
    return await _pk((await _pb({1: 1, 2: {1: ruid, 3: {}, 4: 1, 6: 'en'}})).hex(), '0E15', k, v)

def _pStatus(pkt):
    try:
        data = json.loads(pkt)
        if '5' not in data or 'data' not in data['5']: 
            return {'status': 'OFFLINE', 'status_emoji': '💤', 'description': 'প্লেয়ার অফলাইনে আছেন (Offline)'}
        jd = data['5']['data']
        if '1' not in jd or 'data' not in jd['1']: 
            return {'status': 'OFFLINE', 'status_emoji': '💤', 'description': 'প্লেয়ার অফলাইনে আছেন (Offline)'}
        d = jd['1']['data']
        if '3' not in d or 'data' not in d['3']: 
            return {'status': 'OFFLINE', 'status_emoji': '💤', 'description': 'প্লেয়ার অফলাইনে আছেন (Offline)'}
        
        st = d['3']['data']
        base = {
            1: 'SOLO', 2: 'INSQUAD', 3: 'INGAME', 4: 'IN_ROOM', 5: 'INGAME', 6: 'SOCIAL_ISLAND', 7: 'MATCHMAKING'
        }.get(st, 'OFFLINE')
        
        emoji = {
            'SOLO': '👤', 'INSQUAD': '👥', 'INGAME': '🎮', 'IN_ROOM': '🏠', 'SOCIAL_ISLAND': '🏝️', 'MATCHMAKING': '⏳', 'OFFLINE': '💤'
        }.get(base, '💤')
        
        desc = {
            'SOLO': 'লবিতে একা দাঁড়িয়ে আছেন (Solo in Lobby)',
            'INSQUAD': 'গ্রুপে বা স্কোয়াডে আছেন (In Group/Squad)',
            'INGAME': 'ম্যাচের ভেতরে খেলছেন (In Game/Playing)',
            'IN_ROOM': 'কাস্টম রুমে আছেন (In Custom Room)',
            'SOCIAL_ISLAND': 'সোশ্যাল আইল্যান্ডে আছেন (In Social Island)',
            'MATCHMAKING': 'ম্যাচ স্টার্ট হওয়ার অপেক্ষায় (Matchmaking)',
            'OFFLINE': 'প্লেয়ার অফলাইনে আছেন (Offline)'
        }.get(base, 'প্লেয়ার অফলাইনে আছেন (Offline)')
        
        mode = None
        f14 = d.get('14', {}).get('data') if '14' in d else None
        if f14 == 1: mode = 'TRAINING'
        elif f14 == 2: mode = 'SOCIAL_ISLAND'
            
        m5 = d.get('5', {}).get('data') if '5' in d else None
        m6 = d.get('6', {}).get('data') if '6' in d else None
        mm = {
            (2, 1): 'BR_RANK (র‍্যাঙ্ক ম্যাচ)',
            (5, 23): 'TRAINING (ট্রেনিং গ্রাউন্ড)',
            (6, 15): 'CS_RANK (ক্ল্যাশ স্কোয়াড র‍্যাঙ্ক)',
            (1, 43): 'LONE_WOLF (লোন উলফ)',
            (1, 1): 'BERMUDA (বারমুডা ক্লাসিক)',
            (1, 15): 'CLASH_SQUAD (ক্ল্যাশ স্কোয়াড ক্লাসিক)',
            (1, 29): 'CONVOY_CRUNCH',
            (1, 61): 'FREE_FOR_ALL'
        }
        if (m5, m6) in mm: mode = mm[(m5, m6)]
        
        time_playing = None
        tg = d.get('4', {}).get('data', 0) if '4' in d else 0
        if tg:
            try:
                d_diff = int((datetime.now() - datetime.fromtimestamp(tg)).total_seconds())
                mn = (abs(d_diff) % 3600) // 60
                sc = abs(d_diff) % 60
                time_playing = f"{mn:02d}m {sc:02d}s"
            except Exception: pass
        
        res = {
            'status': base, 'status_emoji': emoji, 'description': desc,
            'details': {'mode': mode, 'time_playing': time_playing}
        }
        
        if base == 'INSQUAD':
            squad_owner = d.get('8', {}).get('data') if '8' in d else None
            team_code = d.get('11', {}).get('data') if '11' in d else None
            gc = d.get('9', {}).get('data', 0) if '9' in d else 0
            cm = d.get('10', {}).get('data', 0) + 1 if '10' in d else 0
            res['details'].update({
                'team_code': str(team_code) if team_code else 'N/A',
                'squad_leader_id': squad_owner if squad_owner else 'N/A',
                'squad_size': f"{gc}/{cm}" if gc else 'N/A'
            })
        elif base == 'IN_ROOM':
            room_id = d.get('15', {}).get('data') if '15' in d else None
            room_owner = d.get('1', {}).get('data') if '1' in d else None
            players_count = f"{d.get('17',{}).get('data',0)}/{d.get('18',{}).get('data',0)}"
            res['details'].update({
                'room_id': room_id, 'room_owner_id': room_owner, 'room_players': players_count
            })
            
        return res
    except Exception:
        return {'status': 'PARSE_ERROR', 'status_emoji': '❌', 'description': 'স্ট্যাটাস পার্সিং ত্রুটি'}

def _pRoom(pkt):
    try:
        data = json.loads(pkt)
        if '5' not in data or 'data' not in data['5']: return None
        jd = data['5']['data']
        if '1' not in jd or 'data' not in jd['1']: return None
        rd = jd['1']['data']
        
        mm = {
            1: 'BERMUDA (বারমুডা ক্লাসিক)', 201: 'BATTLE_CAGE (ব্যাটল কেজ)',
            15: 'CLASH_SQUAD (ক্ল্যাশ স্কোয়াড)', 43: 'LONE_WOLF (লোন উলফ)',
            3: 'RUSH_HOUR', 27: 'BOMB_SQUAD_5V5', 24: 'DEATH_MATCH'
        }
        return {
            'room_id': int(rd['1']['data']) if '1' in rd else None,
            'room_name': rd['2']['data'] if '2' in rd else 'UNKNOWN',
            'owner_uid': int(rd['37']['data']['1']['data']) if '37' in rd and 'data' in rd['37'] else None,
            'mode': mm.get(rd.get('4', {}).get('data'), 'UNKNOWN'),
            'players': f"{rd.get('6',{}).get('data',0)}/{rd.get('7',{}).get('data',0)}",
            'spectators': rd.get('9', {}).get('data', 0),
            'emulator_block': bool(rd.get('17', {}).get('data', 1)),
        }
    except Exception:
        return None

def generate_styled_box(uid, data):
    status = data.get('status', 'OFFLINE')
    emoji = data.get('status_emoji', '💤')
    desc = data.get('description', 'প্লেয়ার অফলাইনে আছেন (Offline)')
    details = data.get('details', {})
    
    box =  "╔═══════════════════════════════════════════════════════════════════════╗\n"
    box += "║                      🌟 WINTER ARIYAN PLAYER STATUS 🌟               ║\n"
    box += "╠═══════════════════════════════════════════════════════════════════════╣\n"
    box += f"  👤 Target UID      :: {uid}\n"
    box += f"  📊 Garena State    :: {emoji} {status}\n"
    box += f"  📝 Description     :: {desc}\n"
    
    if status == 'INGAME':
        box += f"  🎮 Active Mode     :: {details.get('mode', 'N/A')}\n"
        box += f"  ⏱️ Time Playing    :: {details.get('time_playing', 'N/A')}\n"
    elif status == 'INSQUAD':
        box += f"  👥 Team Code       :: {details.get('team_code', 'N/A')}\n"
        box += f"  👑 Squad Leader    :: {details.get('squad_leader_id', 'N/A')}\n"
        box += f"  📊 Squad Size      :: {details.get('squad_size', 'N/A')}\n"
    elif status == 'IN_ROOM':
        box += f"  🏠 Custom Room ID  :: {details.get('room_id', 'N/A')}\n"
        box += f"  👥 Room Players    :: {details.get('room_players', 'N/A')}\n"
        box += f"  👑 Room Owner UID  :: {details.get('room_owner_id', 'N/A')}\n"
        room_info = data.get('room_info')
        if room_info:
            box += f"  🏷️ Room Name       :: {room_info.get('room_name', 'N/A')}\n"
            box += f"  🎮 Room Mode       :: {room_info.get('mode', 'N/A')}\n"
            box += f"  👁️ Spectators      :: {room_info.get('spectators', 0)}\n"
            box += f"  🚫 Emulator Block  :: {'YES' if room_info.get('emulator_block') else 'NO'}\n"
            
    box += "╠═══════════════════════════════════════════════════════════════════════╣\n"
    box += "║                         👑 POWERED BY WINTER ARIYAN 👑                ║\n"
    box += "╚═══════════════════════════════════════════════════════════════════════╝"
    return box

async def _scan(buf, k, v):
    h = buf.hex()
    for mk, pt in [('0f00','0f'),('0e00','0e')]:
        i = h.find(mk)
        if i != -1 and i % 2 == 0: return pt, h[i + 10:]
    if len(buf) > 5:
        pl = buf[5:]; pl = pl[:len(pl) - (len(pl) % 16)]
        if len(pl) >= 16:
            try:
                dc = unpad(AES.new(k, AES.MODE_CBC, v).decrypt(pl), 16).hex()
                for mk, pt in [('0f00','0f'),('0e00','0e')]:
                    i = dc.find(mk)
                    if i != -1 and i % 2 == 0: return pt, dc[i + 10:]
            except Exception: pass
    return None, None

# ==================== ACTIVE BOT SESSION QUERY ====================
async def _query(uid, bot):
    if not bot.is_online or not bot.online_writer:
        return {'status': 'NO_RESPONSE', 'status_emoji': '❌', 'description': 'বট অফলাইন'}
        
    async with bot.query_lock:
        bot.query_future = asyncio.get_event_loop().create_future()
        try:
            pkt = await _stPkt(uid, bot.key, bot.iv)
            bot.online_writer.write(pkt)
            await bot.online_writer.drain()
            buf = await asyncio.wait_for(bot.query_future, timeout=2.0)
        except asyncio.TimeoutError:
            return {'status': 'NO_RESPONSE', 'status_emoji': '❌', 'description': 'সার্ভার রেসপন্স দেয়নি'}
        except Exception as e:
            return {'status': 'PARSE_ERROR', 'status_emoji': '❌', 'description': f'এরর: {e}'}
        finally:
            bot.query_future = None
            
        pt, pl = await _scan(buf, bot.key, bot.iv)
        if pt == '0f':
            raw = await _parse(pl)
            if not raw: return {'status': 'PARSE_ERROR', 'status_emoji': '❌', 'description': 'পার্সিং এরর'}
            info = _pStatus(raw)
            if info.get('status') == 'IN_ROOM' and info.get('details', {}).get('room_id'):
                room_id = info['details']['room_id']
                bot.query_future = asyncio.get_event_loop().create_future()
                try:
                    bot.online_writer.write(await _rmPkt(int(room_id), bot.key, bot.iv))
                    await bot.online_writer.drain()
                    rb = await asyncio.wait_for(bot.query_future, timeout=2.0)
                    rt, rp = await _scan(rb, bot.key, bot.iv)
                    if rt == '0e':
                        rr = await _parse(rp)
                        if rr: info['room_info'] = _pRoom(rr)
                except Exception: pass
                finally: bot.query_future = None
            return info
        return {'status': 'UNKNOWN', 'status_emoji': '❓', 'description': 'অজানা স্ট্যাটাস'}

# ========== LOGIN & AUTH PROTOCOL ==========
async def GeNeRaTeAccAccess(uid, password):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    headers = {
        "Host": "100067.connect.garena.com",
        "User-Agent": "GarenaMSDK/5.5.2P3(SM-A515F;Android 12;en-US;IND;)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "close"
    }
    data = {
        "uid": str(uid),
        "password": str(password),
        "response_type": "token",
        "client_type": "2",
        "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        "client_id": "100067"
    }
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            async with session.post(url, headers=headers, data=data, ssl=False) as resp:
                if resp.status != 200:
                    text_err = await resp.text()
                    return None, None, f"HTTP {resp.status} - {text_err[:60]}"
                res_data = await resp.json()
                open_id = res_data.get("open_id")
                access_token = res_data.get("access_token")
                if not open_id or not access_token:
                    return None, None, f"Empty Tokens: {res_data}"
                return open_id, access_token, None
    except Exception as e: 
        return None, None, f"Network Error: {e}"

async def EncRypTMajoRLoGin(open_id, access_token):
    msg = MajoRLoGinrEq_pb2.MajorLogin()
    msg.event_time = str(datetime.now())[:-7]
    msg.game_name = "free fire"
    msg.platform_id = 2
    msg.client_version = "1.130.22"
    msg.client_version_code = "2024010012"
    msg.system_software = "Android OS 11 / API-30 (RQ3A.210805.001)"
    msg.system_hardware = "Handheld"
    msg.device_type = "Handheld"
    msg.telecom_operator = "Verizon"
    msg.network_operator_a = "Verizon"
    msg.network_type = "WIFI"
    msg.network_type_a = "WIFI"
    msg.screen_width = 1080
    msg.screen_height = 2400
    msg.screen_dpi = "440"
    msg.processor_details = "ARMv8"
    msg.cpu_type = 2
    msg.cpu_architecture = "64"
    msg.memory = 6144
    msg.gpu_renderer = "Adreno (TM) 650"
    msg.gpu_version = "OpenGL ES 3.2 V@1.50"
    msg.graphics_api = "OpenGLES3"
    msg.unique_device_id = f"Google|{os.urandom(16).hex()}"
    msg.client_ip = ""
    msg.language = "en"
    msg.open_id = open_id
    msg.open_id_type = "4"
    msg.login_open_id_type = 4
    msg.access_token = access_token
    msg.login_by = 3
    msg.platform_sdk_id = 2
    msg.origin_platform_type = "4"
    msg.primary_platform_type = "4"
    msg.memory_available.version = 55
    msg.memory_available.hidden_value = 81
    msg.external_storage_total = 128512
    msg.external_storage_available = 42000
    msg.internal_storage_total = 110731
    msg.internal_storage_available = 25000
    msg.game_disk_storage_total = 26628
    msg.game_disk_storage_available = 22000
    msg.external_sdcard_total_storage = 119234
    msg.external_sdcard_avail_storage = 50000
    msg.library_path = "/data/app/~~random/base.apk"
    msg.library_token = "hash|base.apk"
    msg.client_using_version = "7428b253defc164018c604a1ebbfebdf"
    msg.supported_astc_bitset = 16383
    msg.analytics_detail = b"FwQVTgUPX1UaUllDDwcWCRBpWAUOUgsvA1snWlBaO1kFYg=="
    msg.loading_time = 13564
    msg.release_channel = "android"
    msg.channel_type = 3
    msg.reg_avatar = 1
    msg.if_push = 1
    msg.is_vpn = 0
    msg.android_engine_init_flag = 110009
    
    string = msg.SerializeToString()
    key = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
    iv = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pad(string, AES.block_size))

async def MajorLogin(payload):
    url = "https://loginbp.ggpolarbear.com/MajorLogin"
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            async with session.post(url, data=payload, headers=Hr_Login, ssl=False) as resp:
                if resp.status == 200:
                    return await resp.read(), None
                return None, f"HTTP {resp.status}"
    except Exception as e:
        return None, f"MajorLogin Exception: {e}"

async def GetLoginData(base_url, payload, token):
    url = f"{base_url}/GetLoginData"
    headers = Hr_Login.copy()
    headers['Authorization'] = f"Bearer {token}"
    try:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
            async with session.post(url, data=payload, headers=headers, ssl=False) as resp:
                if resp.status == 200:
                    return await resp.read(), None
                return None, f"HTTP {resp.status}"
    except Exception as e: 
        return None, f"GetLoginData Exception ({url}): {e}"

async def xAuThSTarTuP(TarGeT, token, timestamp, key, iv):
    uid_hex = hex(TarGeT)[2:]
    uid_length = len(uid_hex)
    encrypted_timestamp = await DecodE_HeX(timestamp)
    encrypted_account_token = token.encode().hex()
    encrypted_packet = await EnC_PacKeT(encrypted_account_token, key, iv)
    encrypted_packet_length = hex(len(encrypted_packet) // 2)[2:]
    if uid_length == 9: headers = '0000000'
    elif uid_length == 8: headers = '00000000'
    elif uid_length == 10: headers = '000000'
    elif uid_length == 7: headers = '000000000'
    else: headers = '0000000'
    return f"0115{headers}{uid_hex}{encrypted_timestamp}00000{encrypted_packet_length}{encrypted_packet}"

# ========== BOT CLIENT ==========
class FreeFireBot:
    def __init__(self, uid, password, server='bd'):
        self.uid = uid
        self.password = password
        self.server = server
        self.is_running = True
        self.online_writer = None
        self.reader = None
        self.key = None
        self.iv = None
        self.region = None
        self.tasks = []
        self.is_online = False
        self.online_ip = None
        self.online_port = None
        self.auth_token = None
        self.query_future = None
        self.query_lock = asyncio.Lock()
        self.last_error = "None"

    async def close(self):
        self.is_running = False
        if self.online_writer:
            try:
                self.online_writer.close()
                await self.online_writer.wait_closed()
            except Exception: pass
        for t in self.tasks:
            t.cancel()

    async def tcp_online(self, ip, port, auth_token):
        while self.is_running:
            try:
                reader, writer = await asyncio.open_connection(ip, int(port))
                writer.write(bytes.fromhex(auth_token))
                await writer.drain()
                self.reader = reader
                self.online_writer = writer
                self.is_online = True
                print(f"{C_GREEN}[ONLINE]  ✔ Bot {self.uid} LIVE & READY ({self.server.upper()}){C_RESET}")
                
                while self.is_running and self.is_online:
                    try:
                        data = await asyncio.wait_for(self.reader.read(65536), timeout=1.0)
                        if not data: break
                        if self.query_future and not self.query_future.done():
                            pt, _ = await _scan(data, self.key, self.iv)
                            if pt in ('0f', '0e'):
                                self.query_future.set_result(data)
                    except asyncio.TimeoutError: continue
                    except Exception: break
            except Exception as e:
                self.last_error = f"TCP Online Error: {e}"
            
            if self.query_future and not self.query_future.done():
                self.query_future.set_exception(Exception("Socket Closed"))
            self.online_writer = None
            self.reader = None
            self.is_online = False
            print(f"{C_RED}[OFFLINE] ✖ Bot {self.uid} disconnected ({self.server.upper()}). Reconnecting...{C_RESET}")
            await asyncio.sleep(4)

    async def tcp_chat(self, ip, port, auth_token, ready_event):
        while self.is_running:
            try:
                reader, writer = await asyncio.open_connection(ip, int(port))
                writer.write(bytes.fromhex(auth_token))
                await writer.drain()
                ready_event.set()
                while self.is_running:
                    try:
                        data = await asyncio.wait_for(reader.read(4096), timeout=1.0)
                        if not data: break
                    except asyncio.TimeoutError: continue
                    except Exception: break
            except Exception as e:
                pass
            ready_event.set()
            await asyncio.sleep(3)

    async def keep_online_forever(self):
        while self.is_running:
            try:
                # Step 1: OAuth Token
                print(f"{C_CYAN}[AUTH]    -> [{self.uid}] Step 1: Requesting Access Token ({self.server.upper()})...{C_RESET}")
                open_id, access_token, err = await GeNeRaTeAccAccess(self.uid, self.password)
                if not open_id or not access_token:
                    self.last_error = f"OAuth Grant Failed ({err})"
                    print(f"{C_RED}[FAILED]  ✖ [{self.uid}] Step 1: {self.last_error}{C_RESET}")
                    await asyncio.sleep(6)
                    continue

                # Step 2: Major Login
                print(f"{C_CYAN}[AUTH]    -> [{self.uid}] Step 2: Running MajorLogin...{C_RESET}")
                payload = await EncRypTMajoRLoGin(open_id, access_token)
                response, err = await MajorLogin(payload)
                if not response:
                    self.last_error = f"MajorLogin Failed ({err})"
                    print(f"{C_RED}[FAILED]  ✖ [{self.uid}] Step 2: {self.last_error}{C_RESET}")
                    await asyncio.sleep(6)
                    continue

                # Step 3: Gateway Ports
                auth_data = MajoRLoGinrEs_pb2.MajorLoginRes()
                auth_data.ParseFromString(response)
                
                jwt_token = auth_data.token
                base_url = auth_data.url
                
                if not jwt_token or not base_url:
                    self.last_error = "JWT Token or Base URL extraction failed"
                    print(f"{C_RED}[FAILED]  ✖ [{self.uid}] Step 3: {self.last_error}{C_RESET}")
                    await asyncio.sleep(6)
                    continue

                print(f"{C_CYAN}[AUTH]    -> [{self.uid}] Step 3: Fetching Gateway Ports ({base_url})...{C_RESET}")
                login_data, err = await GetLoginData(base_url, payload, jwt_token)
                if not login_data:
                    self.last_error = f"GetLoginData Failed ({err})"
                    print(f"{C_RED}[FAILED]  ✖ [{self.uid}] Step 3: {self.last_error}{C_RESET}")
                    await asyncio.sleep(6)
                    continue

                port_data = PorTs_pb2.GetLoginData()
                port_data.ParseFromString(login_data)

                self.key = auth_data.key
                self.iv = auth_data.iv
                self.region = auth_data.region
                online_ip, online_port = port_data.Online_IP_Port.split(":")
                chat_ip, chat_port = port_data.AccountIP_Port.split(":")

                auth_token = await xAuThSTarTuP(
                    auth_data.account_uid, auth_data.token, auth_data.timestamp, auth_data.key, auth_data.iv
                )
                self.online_ip = online_ip
                self.online_port = int(online_port)
                self.auth_token = auth_token

                # Step 4: Sockets
                print(f"{C_CYAN}[AUTH]    -> [{self.uid}] Step 4: Connecting Gateway TCP ({online_ip}:{online_port})...{C_RESET}")
                ready = asyncio.Event()
                t1 = asyncio.create_task(self.tcp_chat(chat_ip, chat_port, auth_token, ready))
                self.tasks.append(t1)

                try:
                    await asyncio.wait_for(ready.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    pass

                t2 = asyncio.create_task(self.tcp_online(online_ip, online_port, auth_token))
                self.tasks.append(t2)

                if self.server == 'bd':
                    connected_clients_bd[str(self.uid)] = self
                else:
                    connected_clients_ind[str(self.uid)] = self

                await asyncio.gather(t1, t2, return_exceptions=True)
            except Exception as e:
                self.last_error = f"Unexpected Error: {e}"
                print(f"{C_RED}[ERROR]   ✖ [{self.uid}] {self.last_error}{C_RESET}")
            await asyncio.sleep(4)

# ========== LOAD BALANCER & DUAL QUERY ==========
async def get_load_balanced_bot(server="bd"):
    global bd_rr_idx, ind_rr_idx
    async with rr_lock:
        if server == "bd":
            bots = [b for b in connected_clients_bd.values() if b.is_online and b.online_writer]
            if not bots: return None
            bd_rr_idx = (bd_rr_idx + 1) % len(bots)
            return bots[bd_rr_idx]
        elif server == "ind":
            bots = [b for b in connected_clients_ind.values() if b.is_online and b.online_writer]
            if not bots: return None
            ind_rr_idx = (ind_rr_idx + 1) % len(bots)
            return bots[ind_rr_idx]
        else:
            all_bots = [b for b in list(connected_clients_bd.values()) + list(connected_clients_ind.values()) if b.is_online and b.online_writer]
            return random.choice(all_bots) if all_bots else None

async def find_player_and_server(uid):
    bd_bot = await get_load_balanced_bot("bd")
    ind_bot = await get_load_balanced_bot("ind")
    tasks, servers, bots = [], [], []
    
    if bd_bot:
        tasks.append(_query(uid, bd_bot))
        servers.append("bd"); bots.append(bd_bot)
    if ind_bot:
        tasks.append(_query(uid, ind_bot))
        servers.append("ind"); bots.append(ind_bot)
    if not tasks: return None, None, None
        
    results = await asyncio.gather(*tasks, return_exceptions=True)
    best_idx = -1
    for idx, res in enumerate(results):
        if not isinstance(res, Exception) and res.get('status') not in ('OFFLINE', 'PARSE_ERROR', 'UNKNOWN', 'NO_RESPONSE', None):
            best_idx = idx
            break
            
    if best_idx == -1:
        for idx, res in enumerate(results):
            if not isinstance(res, Exception) and res.get('status') != 'NO_RESPONSE':
                best_idx = idx
                break
                
    if best_idx != -1: return servers[best_idx], bots[best_idx], results[best_idx]
    return None, None, None

# ========== 5-MINUTE STRICT SPAM WORKER ==========
async def run_room_spam_loop(uid, server, bot, status_result, duration_minutes, update: Update, sent_msg, user_name):
    start_time = time.time()
    # কঠোরভাবে সর্বোচ্চ ৫ মিনিট (300 সেকেন্ড) ক্যাপড
    duration_minutes = min(duration_minutes, MAX_SESSION_MINUTES)
    total_seconds = duration_minutes * 60
    room_id = status_result['details']['room_id']
    
    active_bot = bot
    packets_sent = 0
    frame_idx = 0
    last_ui_update = 0

    try:
        while time.time() - start_time < total_seconds:
            elapsed = int(time.time() - start_time)
            
            # প্রতি ৫ সেকেন্ড পর পর লাইভ অ্যানিমেশন বক্স মেসেজ এডিট হবে
            if time.time() - last_ui_update >= 5.0:
                frame_idx += 1
                ui_box = generate_live_spam_box(uid, room_id, server, elapsed, total_seconds, packets_sent, frame_idx, user_name)
                try:
                    await sent_msg.edit_text(ui_box, parse_mode="Markdown")
                except TelegramError:
                    pass
                last_ui_update = time.time()

            # সকেট কানেকশন ব্যাকআপ
            if not active_bot.is_online or not active_bot.online_writer:
                fallback = await get_load_balanced_bot(server)
                if not fallback:
                    await asyncio.sleep(1.0); continue
                active_bot = fallback

            # বার্স্ট মোড প্যাকেট ট্রান্সমিশন
            for _ in range(5):
                if time.time() - start_time >= total_seconds:
                    break
                same_val = random.choice([32768])
                avatar = random.choice([902053010, 902053011, 902043024, 902042011, 902043018, 902027027])
                color = get_random_color()
                
                fields = {
                    1: 78,
                    2: {
                        1: int(room_id),
                        2: f"[C][B]{color} ARIYAN",
                        3: {2: 1, 3: 1},
                        4: 330, 5: 6000, 6: 201,
                        10: int(avatar), 11: int(uid), 12: 1,
                        15: {1: 1, 2: same_val}, 16: same_val,
                        18: {1: 11481904755, 2: 8, 3: "\u0010\u0015\b\n\u000b\u0013\f\u000f\u0011\u0004\u0007\u0002\u0003\r\u000e\u0012\u0001\u0005\u0006"},
                        31: {1: 1, 2: same_val}, 32: same_val,
                        34: {1: int(uid), 2: 8, 3: bytes([15,6,21,8,10,11,19,12,17,4,14,20,7,2,1,5,16,3,13,18])}
                    }
                }
                try:
                    pkt = await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0e15', active_bot.key, active_bot.iv)
                    active_bot.online_writer.write(pkt)
                    await active_bot.online_writer.drain()
                    packets_sent += 1
                except Exception: pass
                await asyncio.sleep(0.08)

        # ৫ মিনিট সম্পন্ন হলে ফিনিশিং বক্স
        final_box = generate_completed_spam_box(uid, room_id, server, packets_sent, duration_minutes, user_name)
        await sent_msg.edit_text(final_box, parse_mode="Markdown")

    except asyncio.CancelledError:
        cancel_box = boxed(f"🛑 টার্গেট {uid} এর স্প্যাম সফলভাবে বন্ধ করা হয়েছে!\n📦 মোট প্রেরিত প্যাকেট: {packets_sent:,}", " CANCELLED ")
        await sent_msg.edit_text(cancel_box, parse_mode="Markdown")
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ ত্রুটি: `{e}`")
    finally:
        active_spam_tasks.pop(str(uid), None)

# ========== SYSTEM RESTART FUNCTION ==========
def restart_program():
    """সম্পূর্ণ পাইথন স্ক্রিপ্টটিকে ক্লিন রিস্টার্ট দেয়"""
    print(f"\n{BOLD}{C_RED}🔄 RESTARTING SYSTEM NOW...{C_RESET}")
    # সকল অ্যাক্টিভ টাস্ক ও সকেট বন্ধ করা
    for task in active_spam_tasks.values():
        task.cancel()
    # পাইথন প্রসেস রিস্টার্ট
    os.execv(sys.executable, [sys.executable] + sys.argv)

# ========== TELEGRAM HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_IDS

    text = (
        "🔥 WELCOME TO WINTER ARIYAN BOT 🔥\n\n"
        f"📌 Version: {ob} - {version}\n"
        f"⏱️ সেশন সীমা: প্রতিবারে সর্বোচ্চ {MAX_SESSION_MINUTES} মিনিট\n"
        "⚡ মাল্টি-ইউজার: আনলিমিটেড ইউজার একসাথে চালাতে পারবে!\n\n"
        "👉 `/status` – চেক সক্রিয় সার্ভার বটসমূহ\n"
        "👉 `/status <UID>` – প্লেয়ার লাইভ ইন-গেম স্ট্যাটাস\n"
        "👉 `/room <UID>` – কাস্টম রুমে ৫ মিনিটের লাইভ স্প্যাম\n"
        "👉 `/stop <UID>` – নির্দিষ্ট UID-এর স্প্যাম বন্ধ করুন\n"
    )
    
    if is_admin:
        text += "\n👑 *ADMIN MODE ACTIVATED*\nআপনার জন্য নিচে কুইক বাটন যুক্ত করা হয়েছে।"
        await update.effective_message.reply_text(
            boxed(text, " ARIYAN BOT (ADMIN) "), 
            parse_mode='Markdown',
            reply_markup=get_admin_keyboard()
        )
    else:
        await update.effective_message.reply_text(
            boxed(text, " ARIYAN BOT "), 
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        uid = context.args[0].strip()
        if uid.isdigit():
            sent_msg = await update.effective_message.reply_text("🔍 বাংলাদেশ ও ইন্ডিয়া উভয় সার্ভারে চেক করা হচ্ছে...")
            server, bot, result = await find_player_and_server(uid)
            if server and result:
                box_text = generate_styled_box(uid, result)
                await sent_msg.edit_text(f"🟢 Server: `{server.upper()}`\n\n```\n{box_text}\n```", parse_mode="Markdown")
            else:
                await sent_msg.edit_text("❌ কোনো সার্ভার থেকেই প্লেয়ারের তথ্য পাওয়া যায়নি!")
            return

    total_bd = len(connected_clients_bd)
    total_ind = len(connected_clients_ind)
    bd_online = len([u for u, b in connected_clients_bd.items() if b.is_online])
    ind_online = len([u for u, b in connected_clients_ind.items() if b.is_online])
    
    status_text = (
        f"🇧🇩 BD Active Online  : {bd_online}/{total_bd}\n"
        f"🇮🇳 IND Active Online : {ind_online}/{total_ind}\n\n"
        f"⚡ Active Tasks Running: {len(active_spam_tasks)}\n"
        f"⏱️ Session Rule       : Max {MAX_SESSION_MINUTES} Mins per run\n"
        f"🚀 Concurrency Pool   : UNLIMITED PARALLEL"
    )
    await update.effective_message.reply_text(boxed(status_text, " BOT STATUS "), parse_mode='Markdown')

async def room_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("❌ ব্যবহার বিধি: `/room <UID>`\nউদাহরণ: `/room 5411923563`\n(নোট: প্রতিবার সর্বোচ্চ ৫ মিনিট চলবে)")
        return
        
    uid = context.args[0].strip()
    if not uid.isdigit():
        await update.effective_message.reply_text("❌ সঠিক সংখ্যামূলক UID প্রদান করুন।")
        return
        
    user_name = update.effective_user.username or update.effective_user.first_name or "Player"
    
    # কঠোরভাবে ৫ মিনিট ফিক্সড রাখা হয়েছে
    duration = MAX_SESSION_MINUTES
        
    if str(uid) in active_spam_tasks:
        await update.effective_message.reply_text(f"⚠️ টার্গেট `{uid}` এর ওপর অলরেডি একটি স্প্যাম সেশন লাইভ চলছে!\nবন্ধ করতে `/stop {uid}` লিখুন।")
        return
        
    sent_msg = await update.effective_message.reply_text("🔍 কাস্টম রুম ও ডুয়াল সার্ভার স্ক্যান করা হচ্ছে...")
    server, bot, result = await find_player_and_server(uid)
    
    if server and result:
        status = result.get('status')
        room_id = result.get('details', {}).get('room_id') if status == 'IN_ROOM' else None
        
        if not room_id:
            await sent_msg.edit_text(
                f"❌ প্লেয়ার বর্তমানে কোনো কাস্টম রুমে নেই!\n"
                f"📍 বর্তমান অবস্থান: `{status}` ({result.get('description')})"
            )
            return
            
        task = asyncio.create_task(run_room_spam_loop(uid, server, bot, result, duration, update, sent_msg, user_name))
        active_spam_tasks[str(uid)] = task
    else:
        await sent_msg.edit_text("❌ প্লেয়ারের সচল সেশন পাওয়া যায়নি বা গেম বট অফলাইন!")

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("❌ ব্যবহার বিধি: `/stop <UID>`")
        return
    uid = context.args[0].strip()
    if str(uid) in active_spam_tasks:
        active_spam_tasks[str(uid)].cancel()
        await update.effective_message.reply_text(f"🛑 টার্গেট `{uid}` এর ওপর চলমান স্প্যাম থামানোর অনুরোধ গৃহীত হয়েছে।")
    else:
        await update.effective_message.reply_text(f"❌ টার্গেট `{uid}` এর ওপর কোনো স্প্যামিং সচল নেই!")

async def restart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.effective_message.reply_text("⛔ আপনি এই কমান্ড ব্যবহারের অনুমতিপ্রাপ্ত নন!")
        return
    
    await update.effective_message.reply_text("🔄 বট রিস্টার্ট হচ্ছে... অনুগ্রহ করে ১০-১৫ সেকেন্ড অপেক্ষা করুন।")
    await asyncio.sleep(1)
    restart_program()

# ========== TEXT & BUTTON MESSAGE HANDLER ==========
async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text.strip()
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_IDS

    # এডমিন বাটন ইন্টারঅ্যাকশন
    if is_admin and text == "🔄 Restart Engine":
        await update.effective_message.reply_text("🔄 সমস্ত কানেকশন বন্ধ করে ইঞ্জিন পুনরায় চালু (Restart) করা হচ্ছে...")
        await asyncio.sleep(1)
        restart_program()
        return
        
    elif is_admin and text == "🛑 Stop All Attacks":
        count = len(active_spam_tasks)
        for t in list(active_spam_tasks.values()):
            t.cancel()
        active_spam_tasks.clear()
        await update.effective_message.reply_text(f"🛑 এক ক্লিকে মোট {count} টি অ্যাক্টিভ স্প্যাম বন্ধ করা হয়েছে।")
        return

    elif text == "📊 Server Status":
        await status_cmd(update, context)
        return

    elif text == "❓ Help / Commands":
        await start(update, context)
        return

    # UID দিয়ে সরাসরি কুয়েরি চেক
    if text.isdigit():
        sent_msg = await update.effective_message.reply_text("🔍 বাংলাদেশ ও ইন্ডিয়া উভয় সার্ভারে চেক করা হচ্ছে...")
        server, bot, result = await find_player_and_server(text)
        if server and result:
            box_text = generate_styled_box(text, result)
            await sent_msg.edit_text(f"🟢 Server: `{server.upper()}`\n\n```\n{box_text}\n```", parse_mode="Markdown")
        else:
            await sent_msg.edit_text("❌ কোনো সার্ভার থেকেই প্লেয়ারের তথ্য পাওয়া যায়নি!")
        return

    await update.effective_message.reply_text("❌ অনুগ্রহ করে সঠিক সংখ্যামূলক UID পাঠান বা /room <UID> কমান্ড ব্যবহার করুন।")

# ========== 3. SMOOTH BACKGROUND BOT LOADER ==========
async def load_and_start():
    print(f"\n{BOLD}{C_YELLOW}╔════════════════════════════════════════════════════════════╗{C_RESET}")
    print(f"{BOLD}{C_YELLOW}║      🚀 INITIALIZING DUAL-SERVER ACCOUNT SEQUENCER         ║{C_RESET}")
    print(f"{BOLD}{C_YELLOW}╚════════════════════════════════════════════════════════════╝{C_RESET}\n")
    
    bd_count = 0
    # BD Accounts
    try:
        if os.path.exists("bd.txt"):
            with open("bd.txt", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and ":" in line:
                        uid, pwd = line.split(":")[:2]
                        bot = FreeFireBot(uid=int(uid), password=pwd, server="bd")
                        connected_clients_bd[str(uid)] = bot
                        asyncio.create_task(bot.keep_online_forever())
                        bd_count += 1
                        await asyncio.sleep(1.2)
            print(f"{C_GREEN}✔ Queued {bd_count} BD Accounts from bd.txt{C_RESET}")
        else:
            print(f"{C_RED}✖ bd.txt not found!{C_RESET}")
    except Exception as e:
        print(f"{C_RED}⚠️ Error loading bd.txt: {e}{C_RESET}")

    ind_count = 0
    # IND Accounts
    try:
        if os.path.exists("ind.txt"):
            with open("ind.txt", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and ":" in line:
                        uid, pwd = line.split(":")[:2]
                        bot = FreeFireBot(uid=int(uid), password=pwd, server="ind")
                        connected_clients_ind[str(uid)] = bot
                        asyncio.create_task(bot.keep_online_forever())
                        ind_count += 1
                        await asyncio.sleep(1.2)
            print(f"{C_GREEN}✔ Queued {ind_count} IND Accounts from ind.txt{C_RESET}")
        else:
            print(f"{C_RED}✖ ind.txt not found!{C_RESET}")
    except Exception as e:
        print(f"{C_RED}⚠️ Error loading ind.txt: {e}{C_RESET}")

    # ডায়াগনস্টিক রিপোর্ট প্রিন্টার (প্রতি ৩০ সেকেন্ড)
    async def periodic_status_logger():
        while True:
            await asyncio.sleep(30)
            bd_on = len([b for b in connected_clients_bd.values() if b.is_online])
            ind_on = len([b for b in connected_clients_ind.values() if b.is_online])
            print(f"\n{C_MAGENTA}────────────── [ LIVE BOT POOL SUMMARY ] ──────────────{C_RESET}")
            print(f"  🇧🇩 BD  Online : {C_GREEN}{bd_on}/{len(connected_clients_bd)}{C_RESET}")
            print(f"  🇮🇳 IND Online : {C_GREEN}{ind_on}/{len(connected_clients_ind)}{C_RESET}")
            
            offline_bots = [b for b in list(connected_clients_bd.values()) + list(connected_clients_ind.values()) if not b.is_online]
            if offline_bots:
                print(f"{C_YELLOW}  ⚠️ Offline Account Status Details:{C_RESET}")
                for b in offline_bots:
                    print(f"     • UID: {b.uid} ({b.server.upper()}) -> Reason: {C_RED}{b.last_error}{C_RESET}")
            print(f"{C_MAGENTA}───────────────────────────────────────────────────────{C_RESET}\n")

    # প্রতি ৪ ঘন্টা পর পর স্বয়ংক্রিয় অটো-রিস্টার্ট শিডিউলার
    async def auto_restart_scheduler():
        await asyncio.sleep(AUTO_RESTART_INTERVAL)
        print(f"\n{C_RED}[SCHEDULED] 4 Hours completed! Auto-restarting engine for clean memory & fresh socket...{C_RESET}")
        restart_program()

    asyncio.create_task(periodic_status_logger())
    asyncio.create_task(auto_restart_scheduler())

# ========== 4. POST INIT ==========
async def post_init(application: Application):
    print(f"\n{C_GREEN}🚀 Telegram Bot is now ONLINE & Listening for commands!{C_RESET}")
    asyncio.create_task(load_and_start())

# ========== MAIN ENTRY POINT ==========
def main():
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .job_queue(None)
        .concurrent_updates(True)
        .post_init(post_init)
        .build()
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("room", room_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("restart", restart_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    
    print(f"{C_CYAN}🤖 Winter Ariyan Telegram Multi-User Engine Starting...{C_RESET}")
    print(f"📌 Release Version: {ob} - {version}")
    print(f"⏱️ 4-Hour Auto-Restart Scheduled.")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
