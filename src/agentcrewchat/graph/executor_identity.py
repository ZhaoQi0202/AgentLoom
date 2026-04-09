"""执行 Agent 身份管理：随机中文名 + 性格池 + 主题色分配。"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

# ── 名字池 ──
_FIRST_CHARS = "见瑶辰榆澜悦诗沐云晴芯羽霁霜霓岚"


def generate_executor_name(task_id: str, used: set[str]) -> str:
    """从 task_id 哈希生成随机两字中文名，格式「小X」，不与 used 重复。"""
    seed = int(hashlib.sha256(task_id.encode()).hexdigest(), 16)
    rng = random.Random(seed)
    for _ in range(200):
        first = rng.choice(_FIRST_CHARS)
        candidate = f"小{first}"
        if candidate not in used:
            return candidate
    # 兜底：加数字后缀
    for n in range(2, 100):
        first = rng.choice(_FIRST_CHARS)
        candidate = f"小{first}{n}"
        if candidate not in used:
            return candidate
    return f"小{task_id[:3]}"


# ── 性格池 ──
PERSONALITY_POOL = [
    "急性子", "碎嘴子", "自信派", "谨慎派",
    "乐观派", "毒舌徒弟", "学院派", "佛系",
]

PERSONALITY_PROMPTS: dict[str, str] = {
    "急性子":  "你说话简洁直接，不废话，给结果。",
    "碎嘴子":  "你喜欢解释你的操作过程，说话稍啰嗦但认真负责。",
    "自信派":  "你语气笃定，偶尔自夸一下，但活确实干得漂亮。",
    "谨慎派":  "你经常确认步骤，会标注不确定的地方，做事稳。",
    "乐观派":  "你说话积极向上，喜欢加油打气，遇到问题也不慌。",
    "毒舌徒弟": "你受审核员铁口的影响，偶尔嘴硬但执行力很强。",
    "学院派":  "你喜欢引用方法论，说话偏正式规范。",
    "佛系":    "你什么都说「好的没问题」，但做事很靠谱。",
}


def pick_personality(task_id: str) -> str:
    """根据 task_id 确定性选性格。"""
    idx = int(hashlib.sha256(task_id.encode()).hexdigest(), 16) % len(PERSONALITY_POOL)
    return PERSONALITY_POOL[idx]


# ── 主题色 ──
EXECUTOR_COLOR_PALETTE = [
    "#0891b2", "#16a34a", "#db2777", "#4f46e5",
    "#a16207", "#f97316", "#059669", "#e11d48",
    "#2563eb", "#d97706", "#8b5cf6", "#0284c7",
    "#65a30d", "#475569", "#9f1239",
]

# 不与固定 Agent 主题色重复
_FIXED_COLORS = {"#7c3aed", "#2563eb", "#ea580c"}


def pick_executor_color(task_id: str, used_colors: set[str]) -> str:
    """为执行 Agent 分配主题色。优先从色板取，超 15 个随机 HSL。"""
    available = [c for c in EXECUTOR_COLOR_PALETTE if c not in _FIXED_COLORS and c not in used_colors]
    if available:
        seed = int(hashlib.sha256(task_id.encode()).hexdigest(), 16)
        rng = random.Random(seed)
        return rng.choice(available)
    # 超出 15 色，随机 HSL
    seed = int(hashlib.sha256(task_id.encode()).hexdigest(), 16)
    rng = random.Random(seed)
    h = rng.randint(0, 360)
    # 检查色相距已分配色至少 30°
    for _ in range(100):
        too_close = False
        for uc in used_colors:
            existing_h = _hex_to_hue(uc)
            if existing_h is not None and abs((h - existing_h) % 360) < 30:
                too_close = True
                break
        if not too_close:
            break
        h = rng.randint(0, 360)
    s = rng.randint(60, 80)
    l = rng.randint(40, 55)
    return f"hsl({h}, {s}%, {l}%)"


def _hex_to_hue(hex_color: str) -> float | None:
    """简易 hex → hue 转换，用于色相距离计算。"""
    try:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
        mx, mn = max(r, g, b), min(r, g, b)
        if mx == mn:
            return 0.0
        d = mx - mn
        if mx == r:
            h_deg = 60 * ((g - b) / d % 6)
        elif mx == g:
            h_deg = 60 * ((b - r) / d + 2)
        else:
            h_deg = 60 * ((r - g) / d + 4)
        return h_deg % 360
    except Exception:
        return None


@dataclass
class ExecutorIdentity:
    name: str
    personality: str
    personality_prompt: str
    color: str


def create_executor_identity(
    task_id: str,
    used_names: set[str],
    used_colors: set[str],
) -> ExecutorIdentity:
    """为单个执行任务创建完整身份。"""
    name = generate_executor_name(task_id, used_names)
    used_names.add(name)
    personality = pick_personality(task_id)
    personality_prompt = PERSONALITY_PROMPTS[personality]
    color = pick_executor_color(task_id, used_colors)
    used_colors.add(color)
    return ExecutorIdentity(
        name=name,
        personality=personality,
        personality_prompt=personality_prompt,
        color=color,
    )
