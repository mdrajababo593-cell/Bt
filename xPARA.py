# By RedZed PARAHEX (Updated Level Bypass & Ghost)

import requests, json, binascii, time, urllib3, base64, datetime, re, socket, threading, random, os, asyncio
from protobuf_decoder.protobuf_decoder import Parser
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from datetime import datetime
from google.protobuf.timestamp_pb2 import Timestamp

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

Key , Iv = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56]) , bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

async def EnC_AEs(HeX):
    cipher = AES.new(Key , AES.MODE_CBC , Iv)
    return cipher.encrypt(pad(bytes.fromhex(HeX), AES.block_size)).hex()
    
async def DEc_AEs(HeX):
    cipher = AES.new(Key , AES.MODE_CBC , Iv)
    return unpad(cipher.decrypt(bytes.fromhex(HeX)), AES.block_size).hex()
    
async def EnC_PacKeT(HeX , K , V): 
    return AES.new(K , AES.MODE_CBC , V).encrypt(pad(bytes.fromhex(HeX) ,16)).hex()
    
async def DEc_PacKeT(HeX , K , V):
    return unpad(AES.new(K , AES.MODE_CBC , V).decrypt(bytes.fromhex(HeX)) , 16).hex()  

async def EnC_Uid(H , Tp):
    e , H = [] , int(H)
    while H:
        e.append((H & 0x7F) | (0x80 if H > 0x7F else 0)) ; H >>= 7
    return bytes(e).hex() if Tp == 'Uid' else None

async def EnC_Vr(N):
    if N < 0: ''
    H = []
    while True:
        RedZed = N & 0x7F ; N >>= 7
        if N: RedZed |= 0x80
        H.append(RedZed)
        if not N: break
    return bytes(H)
    
def DEc_Uid(H):
    n = s = 0
    for b in bytes.fromhex(H):
        n |= (b & 0x7F) << s
        if not b & 0x80: break
        s += 7
    return n
    
async def CrEaTe_VarianT(field_number, value):
    field_header = (field_number << 3) | 0
    return await EnC_Vr(field_header) + await EnC_Vr(value)

async def CrEaTe_LenGTh(field_number, value):
    field_header = (field_number << 3) | 2
    encoded_value = value.encode() if isinstance(value, str) else value
    return await EnC_Vr(field_header) + await EnC_Vr(len(encoded_value)) + encoded_value

async def CrEaTe_ProTo(fields):
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(value, dict):
            nested_packet = await CrEaTe_ProTo(value)
            packet.extend(await CrEaTe_LenGTh(field, nested_packet))
        elif isinstance(value, int):
            packet.extend(await CrEaTe_VarianT(field, value))
        elif isinstance(value, str) or isinstance(value, bytes):
            packet.extend(await CrEaTe_LenGTh(field, value))
    return packet
    
async def DecodE_HeX(H):
    R = hex(H) 
    F = str(R)[2:]
    if len(F) == 1: F = "0" + F ; return F
    else: return F

async def Fix_PackEt(parsed_results):
    result_dict = {}
    for result in parsed_results:
        field_data = {}
        field_data['wire_type'] = result.wire_type
        if result.wire_type == "varint":
            field_data['data'] = result.data
        if result.wire_type == "string":
            field_data['data'] = result.data
        if result.wire_type == "bytes":
            field_data['data'] = result.data
        elif result.wire_type == 'length_delimited':
            field_data["data"] = await Fix_PackEt(result.data.results)
        result_dict[result.field] = field_data
    return result_dict

async def EnC_UiDInFo(uid):
    fields = {1:int(uid)}
    uid = await CrEaTe_ProTo(fields)
    uid = uid.hex()
    uid = str(uid)[2:]
    return uid

async def SendInFoPaCKeT(uid , key , iv):
    uid = await EnC_UiDInFo(int(uid))
    hex = f"080112090A05{uid}1005"
    return await GeneRaTePk((hex) , '0F15' , key , iv)

async def SendRoomInfo(roomuid , key , iv):
    fields = {
    1: 1,
    2: {
        1: roomuid,
        3: {},
        4: 1,
        6: "en"
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex() , '0E15' , key , iv)

async def GLobaL(T, K, V):
    fields = {1: 3, 2: {2: 5, 3: f"{T}"}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '1215', K, V)

async def RedZed_3alamyia_Chat(uid, code, K, I):
    fields = {
        1: 3,
        2: {
            1: uid,
            3: "fr",
            4: str(code)
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '1215', K, I)

async def quit_caht_redzed(uid, K, I):
    fields = {
        1: 4,
        2: {
            1: uid,
            3: "fr"
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '1215', K, I)

async def RedZed_SendMsg(msg, owner, bot, K, I):
    fields = {
        1: 1,
        2: 2,
        2: {
            1: bot,
            2: owner,
            4: msg,
            5: str(int(time.time())),
            9: {
                1: "Fun1w5a2",
                2: await xBunnEr(),
                3: 909000024,
                4: 330,
                5: 909000024,
                10: 1,
                11: 1,
                7: 2,
                13: {1: 2},
                14: {
                    1: bot,
                    2: 8,
                    3: b""
                }
            },
            10: "fr",
            13: {
                2: 1,
                3: 1
            },
            14: {}
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '1215', K, I)

async def xBunnEr():
    bN = [902000306 , 902000305 , 902000003 , 902000016 , 902000017 , 902000019 , 902031010 , 902043025 , 902043024 , 902000020 , 902000021 , 902000023 , 902000070 , 902000087 , 902000108 , 902000011 , 902049020 , 902049018 , 902049017 , 902049016 , 902049015 , 902049003 , 902033016 , 902033017 , 902033018 , 902048018 , 902000306 , 902000305 , 902000079]
    return random.choice(bN)

async def xSEndMsg(Msg , Tp , Tp2 , id , K , V):
    feilds = {1: id , 2: Tp2 , 3: Tp, 4: Msg, 5: int(time.time()), 7: 2, 9: {1: "RedZedTOP1", 2: int(await xBunnEr()), 3: 901048018, 4: 330, 5: 909034009, 8: "RedZedTOP1", 10: 1, 11: 1, 13: {1: 2}, 14: {1: 12484827014, 2: 8, 3: b"\x10\x15\x08\n\x0b\x13\x0c\x0f\x11\x04\x07\x02\x03\r\x0e\x12\x01\x05\x06"}, 12: 0}, 10: "en", 13: {3: 1}}
    Pk = (await CrEaTe_ProTo(feilds)).hex()
    Pk = "080112" + await EnC_Uid(len(Pk) // 2, Tp='Uid') + Pk
    return await GeneRaTePk(Pk, '1215', K, V)
    
async def xSEndMsgsQ(Msg , id , K , V):
    fields = {1: id , 2: id , 4: Msg , 5: int(time.time()), 7: 2, 8: 904990072, 9: {1: "RedZedTOP1", 2: await xBunnEr(), 4: 330, 5: 827001005, 8: "RedZedTOP1", 10: 1, 11: 1, 13: {1: 2}, 14: {1: 1158053040, 2: 8, 3: b"\x10\x15\x08\n\x0b\x15\x0c\x0f\x11\x04\x07\x02\x03\r\x0e\x12\x01\x05\x06"}}, 10: "en", 13: {2: 2, 3: 1}}
    Pk = (await CrEaTe_ProTo(fields)).hex()
    Pk = "080112" + await EnC_Uid(len(Pk) // 2, Tp='Uid') + Pk
    return await GeneRaTePk(Pk, '1215', K, V)     

async def AuthClan(CLan_Uid, AuTh, K, V):
    fields = {1: 3, 2: {1: int(CLan_Uid), 2: 1, 4: str(AuTh)}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex() , '1215' , K , V)

async def RedZedLeaveRoom(uid,key,iv):
    fields = {1: 6, 2: {1: uid}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0E15', key , iv)

async def RedZedJoinRomm(uid,password,key,iv):
    fields = {1: 3, 2: {1: int(uid), 2: str(password), 8: {1: "IDC3", 2: 149, 3: "ME"}, 9: b"\x01\x03\x04\x07\t\n\x0b\x12\x0e\x16\x19 \x1d", 10: 1, 12: {}, 13: 1, 14: 1, 16: "en", 22: {1: 21}}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex() , '0E15' , key , iv)

async def new_lag(K,I):
    fields = {1: 15, 2: {1: 804266360, 2: 1}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex() , '0515' , K , I)

async def RedZedRefuse(owner,uid, K,V):
    fields = {1: 5, 2: {1: int(owner), 2: 1, 3: int(uid), 4: "[FF0000][B][C] BOT PARAHEX !"}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex() , '0515' , K , V)

async def RedZed_SendInv(uid,K,V):
    fields = {1: 33, 2: {1: int(uid), 2: "ME", 3: 1, 4: 1, 6: "RedZedKing!!", 7: 330, 8: 1000, 9: 100, 10: "DZ", 12: 1, 13: int(uid), 16: 1, 17: {2: 159, 4: "y[WW", 6: 11, 8: "1.118.1", 9: 3, 10: 1}, 18: 306, 19: 18, 24: 902000306, 26: {}, 27: {1: 11, 2: 12999994075, 3: 999}, 28: {}, 31: {1: 1, 2: 32768}, 32: 32768, 34: {1: 12947882969, 2: 8, 3: b"\x10\x15\x08\n\x0b\x13\x0c\x0f\x11\x04\x07\x02\x03\r\x0e\x12\x01\x05\x06"}}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex() , '0515' , K , V)

async def GeT_Status(PLayer_Uid , K , V):
    PLayer_Uid = await EnC_Uid(PLayer_Uid , Tp = 'Uid')
    if len(PLayer_Uid) == 8: Pk = f'080112080a04{PLayer_Uid}1005'
    elif len(PLayer_Uid) == 10: Pk = f"080112090a05{PLayer_Uid}1005"
    return await GeneRaTePk(Pk , '0f15' , K , V)

# ---- লেভেল লিমিট বাইপাস করে সরাসরি জয়েন প্যাকেট ----
async def GenJoinSquadsPacket(code,  K , V):
    fields = {
        1: 4,
        2: {
            4: bytes.fromhex("01090a0b121920"),
            5: str(code),
            6: 6,
            8: 1,
            9: {
                2: 800,
                6: 11,
                8: "1.123.1", # গেমের লেটেস্ট ভার্সন
                9: 5,
                10: 1
            }
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex() , '0515' , K , V)

async def Emote_k(TarGeT , idT, K, V):
    fields = {1: 21, 2: {1: 804266360, 2: 909000001, 5: {1: TarGeT, 3: idT}}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex() , '0515' , K , V)

async def FS(K,V):
    fields = {1: 9, 2: {1: 13250133060}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex() , '0515' , K , V)

# ---- ফেক লেভেল (15) সেট করা নতুন ঘোস্ট প্যাকেট ----
async def ghost_pakcet(player_id , nm , secret_code , key ,iv):
    fields = {
        1: 61,
        2: {
            1: int(player_id),  
            2: {
                1: int(player_id),  
                2: int(time.time()),  
                3: f"{nm}",
                5: 12,  
                6: 15,  # Anti-cheat bypass (Fake Level 15 instead of 9999999)
                7: 1,
                8: {
                    2: 1,
                    3: 1,
                },
                9: 3,
            },
            3: secret_code,
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex() , '0515' , key ,iv)

async def GeneRaTePk(Pk , N , K , V):
    PkEnc = await EnC_PacKeT(Pk , K , V)
    _ = await DecodE_HeX(int(len(PkEnc) // 2))
    if len(_) == 2: HeadEr = N + "000000"
    elif len(_) == 3: HeadEr = N + "00000"
    elif len(_) == 4: HeadEr = N + "0000"
    elif len(_) == 5: HeadEr = N + "000"
    else: HeadEr = N + "000000"
    return bytes.fromhex(HeadEr + _ + PkEnc)

async def OpEnSq(K , V):
    fields = {1: 1, 2: {2: b"\x01", 3: 1, 4: 1, 5: "en", 9: 1, 11: 1, 13: 1, 14: {2: 5756, 6: 11, 8: "1.111.5", 9: 2, 10: 4}}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex() , '0515' , K , V) 

async def cHSq(Nu , Uid , K , V):
    fields = {1: 17, 2: {1: int(Uid), 2: 1, 3: int(Nu - 1), 4: 62, 5: b"\x1a", 8: 5, 13: 329}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex() , '0515' , K , V) 

async def SEnd_InV(Nu , Uid , K , V):
    fields = {1: 2 , 2: {1: int(Uid) , 2: "ME" , 4: int(Nu)}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex() , '0515' , K , V) 
    
async def ExiT(idT , K , V):
    fields = {1: 7, 2: {1: idT}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex() , '0515' , K , V)