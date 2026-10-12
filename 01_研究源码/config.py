"""config.py — 配置常量 & 辅助函数"""
import os

MAP_FILE = "Map.json"
AGENT_FILE = "Agent.json"

LLM_PROVIDERS = {
    "Poe": {
        "base": "https://api.poe.com",
        "env_key": "POE_API_KEY",
        "models": [
            "GPT-4o", "gpt-5.4-pro", "claude-sonnet-4.6",
            "gemini-3.1-pro", "glm-5", "minimax-m2.7",
            "grok-4", "Llama-3.1-70B",
        ],
        "reasoning_field": None,
        "note": "Poe聚合平台，一个Key调多家模型",
    },
    "DeepSeek": {
        "base": "https://api.deepseek.com",
        "env_key": "DEEPSEEK_API_KEY",
        "models": [
            "deepseek-v4-flash", "deepseek-chat", "deepseek-reasoner"
        ],
        "reasoning_field": "reasoning_content",
        "note": "Chat快速；Reasoner含推理链(R1)",
    },
    "OpenAI": {
        "base": "https://api.openai.com",
        "env_key": "OPENAI_API_KEY",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        "reasoning_field": None,
        "note": "GPT-4o综合能力强",
    },
    "Google Gemini": {
        "base": "https://generativelanguage.googleapis.com",
        "env_key": "GEMINI_API_KEY",
        "models": [
            "gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash",
            "gemini-2.0-flash-thinking-exp", "gemini-2.5-pro-preview",
        ],
        "reasoning_field": None,
        "thinking_models": {"gemini-2.0-flash-thinking-exp", "gemini-2.5-pro-preview"},
        "note": "thinking/2.5-pro支持思维链",
    },
    "Alibaba Qwen": {
        "base": "https://dashscope.aliyuncs.com/compatible-mode",
        "env_key": "DASHSCOPE_API_KEY",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo"],
        "reasoning_field": None,
        "note": "中文优化",
    },
    "ByteDance Doubao": {
        "base": "https://ark.cn-beijing.volces.com/api",
        "env_key": "ARK_API_KEY",
        "models": ["doubao-pro-32k", "doubao-lite-32k"],
        "reasoning_field": None,
        "note": "豆包",
    },
    "Anthropic Claude": {
        "base": "https://api.anthropic.com",
        "env_key": "ANTHROPIC_API_KEY",
        "models": ["claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-4-5"],
        "reasoning_field": None,
        "note": "Sonnet均衡；Opus最强",
    },
    "MiniMax": {
        "base": "https://api.minimax.chat",
        "env_key": "MINIMAX_API_KEY",
        "models": ["MiniMax-Text-01", "abab6.5s-chat", "abab6.5g-chat"],
        "reasoning_field": None,
        "note": "长文本模型",
    },
}

DEFAULT_PROVIDER = "DeepSeek"
DEFAULT_API_KEY = os.getenv(LLM_PROVIDERS[DEFAULT_PROVIDER]["env_key"], "")

FORBIDDEN_START_NODES = {"N10", "N11", "N12", "N15", "N16", "N18"}
VALID_START_NODES = {"N02", "N03", "N04", "N05", "N06", "N07", "N13"}

CELL = 52
GRID_W = 20
GRID_H = 20
STEP_SECONDS = 5

ROOM_LAYOUT = {
    "N01": (7, 1, 4, 2, "主大厅（火源）", "fire"),
    "N02": (7, 4, 4, 2, "主展廊", "corridor"),
    "N03": (12, 1, 4, 3, "文物展室", "room"),
    "N04": (12, 5, 4, 2, "东侧走廊", "corridor"),
    "N05": (4, 7, 6, 4, "核心展厅", "hall"),
    "N06": (0, 7, 4, 3, "印象派展室", "room"),
    "N07": (11, 7, 4, 2, "北侧长廊", "corridor"),
    "N08": (0, 11, 4, 3, "雕塑展室", "room"),
    "N09": (6, 12, 3, 2, "防火暗门", "door"),
    "N10": (6, 15, 3, 2, "紧急通道", "corridor"),
    "N11": (0, 15, 5, 2, "侧门出口", "exit"),
    "N12": (12, 9, 5, 5, "中庭花园（死胡同）", "deadend"),
    "N13": (11, 4, 4, 2, "临时展室", "room"),
    "N14": (15, 9, 4, 3, "后侧走廊", "corridor"),
    "N15": (15, 13, 4, 2, "封闭院落（死胡同）", "deadend"),   # 原来是 exit，改为 deadend,
    "N16": (15, 16, 3, 2, "储藏室（死胡同）", "deadend"),
    "N17": (0, 4, 4, 2, "西侧走廊", "corridor"),
    "N18": (0,  1,  4, 3, "员工出口",           "exit"),      # 原来是 deadend，改为 exit
}

CORRIDOR_PATHS = {
    ("N01", "N02"): [(9, 3)],
    ("N02", "N05"): [(6, 6), (6, 7)],
    ("N02", "N03"): [(11, 2)],
    ("N03", "N04"): [(14, 4), (14, 5)],
    ("N04", "N13"): [(13, 5)],
    ("N05", "N06"): [(4, 9)],
    ("N05", "N07"): [(10, 9), (11, 9)],
    ("N05", "N09"): [(7, 11), (7, 12)],
    ("N05", "N17"): [(4, 6), (2, 6), (2, 5)],
    ("N06", "N08"): [(2, 10), (2, 11)],
    ("N07", "N12"): [(13, 8), (13, 9)],
    ("N07", "N13"): [(13, 7), (13, 5)],
    ("N08", "N11"): [(2, 14), (2, 15)],
    ("N09", "N10"): [(7, 14), (7, 15)],
    ("N10", "N11"): [(5, 16), (4, 16)],
    ("N13", "N14"): [(15, 5), (15, 9)],
    ("N14", "N15"): [(17, 12), (17, 13)],
    ("N14", "N16"): [(16, 12), (16, 16)],
    ("N17", "N18"): [(2, 3), (2, 1)],
    ("N17", "N14"): [(2, 6), (4, 6), (15, 9)],
}

TYPE_CFG = {
    "Cognitive":  {"emoji": "🔷", "color": "#2563EB", "stroke": "#1D4ED8", "shape": "diamond"},
    "Perceptual": {"emoji": "🔶", "color": "#D97706", "stroke": "#B45309", "shape": "circle"},
    "Follower":   {"emoji": "🔴", "color": "#DC2626", "stroke": "#B91C1C", "shape": "square"},
}

STATUS_COLOR = {
    "Active": None, "Escaped": "#16A34A", "Dead": "#6B7280", "Exhausted": "#9CA3AF",
}

INITIAL_PANIC = {"Cognitive": 0.08, "Perceptual": 0.20, "Follower": 0.38}

ROOM_FILL = {
    "fire": "#FEF2F2", "corridor": "#EFF6FF", "hall": "#EEF2FF",
    "room": "#ECFEFF", "door": "#FAF5FF", "stairs": "#F0FDFA",
    "exit": "#F0FDF4", "deadend": "#FFFBEB",
}

ROOM_ACCENT = {
    "fire": ("#EF4444", "🔥"), "corridor": ("#3B82F6", "🏃"),
    "hall": ("#6366F1", "🏛"), "room": ("#06B6D4", "🖼"),
    "door": ("#A855F7", "🚪"), "stairs": ("#14B8A6", "🪜"),
    "exit": ("#22C55E", "✅"), "deadend": ("#F59E0B", "⛔"),
}


# ── 辅助函数 ──
def risk_to_sense(r):
    if r > 0.75: return "浓烟滚滚、极度危险"
    if r > 0.55: return "烟雾弥漫、呼吸困难"
    if r > 0.35: return "轻微烟味、感觉不安"
    if r > 0.15: return "空气尚可、略有异味"
    return "空气清新、暂时安全"

def density_to_sense(d):
    if d > 3.0: return "极度拥堵，几乎无法移动"
    if d > 1.5: return "非常拥挤"
    if d > 0.7: return "有些拥挤"
    if d > 0.2: return "人不多"
    return "几乎没人"

def dist_to_sense(d):
    if d <= 4: return "较近"
    if d <= 8: return "稍远"
    if d <= 12: return "较远"
    return "很远"

# 修改后
def node_hint(node):
    status = node.get("status", "Open")
    ntype  = node.get("type", "").lower()

    if status == "Blocked":
        return "浓烟封堵，热浪灼人，无法通行"
    if status == "Risky":
        return "烟雾弥漫，能见度极低，呼吸困难，需谨慎"

    hints = {
        "exit":     "门缝透着光，能听到外面的声音，像是出口",
        "stairs":   "能听到脚步声回响，墙上有荧光疏散标识",
        "door":     "有防火门，门上有推杆装置，旁边有指示灯",
        "fire":     "火焰清晰可见、热浪扑面，无法靠近",
        "deadend":  "空间开阔，灯光充足，看起来像是通向外部",
        "corridor": "宽阔走廊，能看到远处的指示牌",
        "hall":     "开阔大厅，隐约听到人群脚步声",
        "room":     "展示房间，空间有限",
    }
    return hints.get(ntype, "普通区域")
