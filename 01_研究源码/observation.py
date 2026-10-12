"""Pure language mappings for auditable local evacuation observations."""


ARCHETYPE_GUIDANCE = {
    "Cognitive": (
        "结合可见烟雾、疏散线索和拥堵判断；在信息不足时保持谨慎，"
        "不要假定自己知道完整地图。"
    ),
    "Perceptual": (
        "主要依据当前能看到的照明、开敞感、门和人群线索判断；"
        "能见度下降时允许出现犹豫。"
    ),
    "Follower": (
        "紧张时更关注可见的人群流向；无人可跟随时依据近处空间线索判断，"
        "可能犹豫或折返。"
    ),
}


def smoke_state(smoke, status="Open"):
    """Map smoke density and passability to one non-contradictory phrase."""
    smoke = max(0.0, min(1.0, float(smoke)))
    if status in {"Blocked", "Deadly"}:
        return "严重浓烟和热风险，无法通行"
    if smoke < 0.20:
        return "空气清晰"
    if smoke < 0.40:
        return "轻微烟雾或异味"
    if smoke < 0.60:
        return "可见烟雾，能见度下降"
    if smoke < 0.80:
        return "浓烟，呼吸困难"
    return "严重浓烟和热风险"


def body_state(health, stamina):
    """Describe health and stamina as separate observable dimensions."""
    health = float(health)
    stamina = float(stamina)
    if health < 40:
        health_text = "烟雾伤害严重"
    elif health < 70:
        health_text = "身体有些虚弱"
    else:
        health_text = "健康状况良好"

    if stamina < 30:
        stamina_text = "体力接近耗尽"
    elif stamina < 60:
        stamina_text = "明显疲劳"
    else:
        stamina_text = "体力尚可"
    return f"{health_text}；{stamina_text}"


def panic_state(panic):
    """Describe current panic without assigning an undeclared diagnosis."""
    panic = max(0.0, min(1.0, float(panic)))
    if panic > 0.70:
        return "高度紧张，判断容易受干扰"
    if panic > 0.40:
        return "有些紧张"
    return "尚能冷静判断"


def static_cue_text(node):
    """Return hazard-neutral local spatial cues declared by the map."""
    cues = node.get("static_cues", [])
    if isinstance(cues, str):
        cues = [cues]
    clean = [str(cue).strip() for cue in cues if str(cue).strip()]
    return "；".join(clean) if clean else "没有明显的额外空间线索"


def archetype_guidance(agent_type):
    """Return conditional guidance for a stable behaviour archetype ID."""
    return ARCHETYPE_GUIDANCE.get(
        agent_type,
        "仅依据当前可见的局部线索判断，不要假定自己知道完整地图。",
    )
