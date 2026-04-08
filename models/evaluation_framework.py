"""Shared evaluation framework metadata for reviewer-facing explanations."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


DIMENSION_ORDER = ("structure", "stroke", "integrity", "stability")

DIMENSION_FRAMEWORK = {
    "structure": {
        "key": "structure",
        "label": "结构",
        "core_question": "字形重心、比例和空间分布是否稳定。",
        "observation_points": [
            "重心是否偏移",
            "字框比例是否合适",
            "上下左右留白是否失衡",
            "主要部件是否集中在有效书写区域",
        ],
        "feature_mapping": [
            "center_quality",
            "bbox_ratio",
            "projection_balance",
            "bbox_fill",
        ],
        "practice_tip": "先用米字格观察重心，再调整主笔与中轴位置。",
    },
    "stroke": {
        "key": "stroke",
        "label": "笔画",
        "core_question": "笔画粗细、走向和连接控制是否稳定。",
        "observation_points": [
            "笔画粗细是否波动过大",
            "横竖撇捺走向是否清晰",
            "线条边缘是否毛糙",
            "笔画关系是否松散或拥挤",
        ],
        "feature_mapping": [
            "texture_std",
            "orientation_concentration",
            "ink_ratio",
            "component_norm",
        ],
        "practice_tip": "先放慢书写速度，保证主笔起收清楚，再追求速度和连贯。",
    },
    "integrity": {
        "key": "integrity",
        "label": "完整",
        "core_question": "单字主体是否完整、清晰、便于稳定识别。",
        "observation_points": [
            "是否有缺笔、断裂或粘连",
            "主体是否碰边",
            "画面是否只保留单字主体",
            "OCR 是否能稳定识别当前单字",
        ],
        "feature_mapping": [
            "ocr_confidence",
            "dominant_share",
            "edge_touch",
            "subject_edge_safe",
        ],
        "practice_tip": "先保证单字完整入框，再减少遮挡、反光和背景干扰。",
    },
    "stability": {
        "key": "stability",
        "label": "稳定",
        "core_question": "本次评测结果是否稳定、可信、适合进入长期统计。",
        "observation_points": [
            "主分与等级是否落在合理区间",
            "模型概率是否集中",
            "解释特征是否整体协调",
            "近几次评测是否处于同一水平带",
        ],
        "feature_mapping": [
            "quality_confidence_norm",
            "probability_margin_norm",
            "feature_quality",
            "score_range_fit",
        ],
        "practice_tip": "保持同样的拍摄方式与书写节奏，连续观察 3 到 5 次结果波动。",
    },
}

AUTHORITY_REFERENCES = [
    {
        "title": "《中小学书法教育指导纲要》",
        "organization": "教育部",
        "role": "用于限定规范书写、课堂训练与初学阶段的评价边界。",
    },
    {
        "title": "《义务教育语文课程标准（2022 年版）》中的规范汉字书写要求",
        "organization": "教育部",
        "role": "用于说明当前系统更适合服务规范字书写与单字练习场景。",
    },
    {
        "title": "书法教学中的常见观察维度",
        "organization": "项目方法论抽象",
        "role": "将结构、笔画、完整和稳定这些课堂语汇映射成可计算特征。",
    },
]

FRAMEWORK_OVERVIEW = {
    "project_position": "面向楷书单字练习的辅助评测系统，而不是替代专家终评的自动考级器。",
    "current_scope": "当前阶段聚焦楷书单字、初学者练习、设备端即时反馈。",
    "boundary_note": "四维分属于解释层，用于提示练习方向，不直接替代教师评分或正式等级认定。",
    "target_users": ["初学者", "课程展示", "教师辅助点评", "设备端快速回看"],
    "current_scripts": ["楷书"],
    "roadmap_scripts": ["行书", "隶书"],
}

VALIDATION_PLAN = {
    "current_stage": "Stage 1 / 楷书单字辅助评测",
    "next_milestone": "完成带人工对照标签的数据扩充，并引入教师校核。",
    "label_target": 500,
    "expert_review_target": 3,
    "trial_user_target": 20,
    "manual_review_policy": [
        "保留人工评分对照表，不把四维分包装成官方等级分。",
        "记录设备来源、时间分布和高频练习字，用于后续样本分析。",
        "优先验证总分与人工判断的一致性，再逐步校准四维解释。",
    ],
}


def get_dimension_basis(scores: dict[str, int] | None = None) -> list[dict[str, Any]]:
    """Return ordered dimension basis cards with optional score values."""

    ordered_items: list[dict[str, Any]] = []
    for key in DIMENSION_ORDER:
        item = deepcopy(DIMENSION_FRAMEWORK[key])
        if scores and scores.get(key) is not None:
            item["score"] = int(scores[key])
        ordered_items.append(item)
    return ordered_items


def build_practice_profile(
    dimension_scores: dict[str, int] | None,
    *,
    total_score: int,
    quality_level: str,
    character_name: str | None = None,
) -> dict[str, Any]:
    """Generate beginner-friendly guidance from the weakest dimension."""

    if not dimension_scores:
        return {
            "stage_key": "foundation",
            "stage_label": "基础观察阶段",
            "scope_note": FRAMEWORK_OVERVIEW["boundary_note"],
            "coach_prompt": "先完成稳定拍摄与单字入框，再积累可比较的连续记录。",
            "best_dimension": None,
            "focus_dimension": None,
            "next_actions": [
                "保证单字完整入框，避免背景干扰。",
                "连续记录 3 次以上结果，观察分数是否稳定。",
                "先以楷书单字为主，不要同时切换多种字体。",
            ],
        }

    ranked = sorted(
        ((key, int(value)) for key, value in dimension_scores.items() if value is not None),
        key=lambda item: (-item[1], DIMENSION_ORDER.index(item[0])),
    )
    best_key, best_score = ranked[0]
    weak_key, weak_score = sorted(
        ranked,
        key=lambda item: (item[1], DIMENSION_ORDER.index(item[0])),
    )[0]

    if total_score >= 85 and quality_level == "good":
        stage_key = "refine"
        stage_label = "巩固提升阶段"
        stage_goal = "在保持当前稳定性的前提下，继续优化细节与一致性。"
    elif total_score >= 70:
        stage_key = "stabilize"
        stage_label = "结构收紧阶段"
        stage_goal = "重点收紧弱项维度，让整体表现更稳定。"
    else:
        stage_key = "foundation"
        stage_label = "基础回正阶段"
        stage_goal = "先把主体写完整、拍清楚，再追求更高分数。"

    best_meta = DIMENSION_FRAMEWORK[best_key]
    weak_meta = DIMENSION_FRAMEWORK[weak_key]
    char_label = f"“{character_name}”" if character_name else "当前单字"
    coach_prompt = (
        f"{char_label}本次最需要优先提升的是{weak_meta['label']}，"
        f"同时保留已经较稳的{best_meta['label']}表现。"
    )

    return {
        "stage_key": stage_key,
        "stage_label": stage_label,
        "stage_goal": stage_goal,
        "scope_note": FRAMEWORK_OVERVIEW["boundary_note"],
        "coach_prompt": coach_prompt,
        "best_dimension": {
            "key": best_key,
            "label": best_meta["label"],
            "score": best_score,
            "tip": best_meta["practice_tip"],
        },
        "focus_dimension": {
            "key": weak_key,
            "label": weak_meta["label"],
            "score": weak_score,
            "tip": weak_meta["practice_tip"],
        },
        "next_actions": [
            f"先围绕{weak_meta['label']}做 3 到 5 次连续练习，观察波动是否缩小。",
            weak_meta["practice_tip"],
            f"保留{best_meta['label']}当前的书写方式，避免同时大幅改变所有笔画。",
        ],
    }


def build_validation_snapshot(summary: dict[str, Any] | None) -> dict[str, Any]:
    """Convert live summary counts into a reviewer-friendly evidence snapshot."""

    summary = summary or {}
    total = int(summary.get("total") or 0)
    unique_characters = int(summary.get("unique_characters") or 0)
    device_count = int(summary.get("device_count") or 0)
    recent_total = int(summary.get("recent_total") or 0)
    label_target = int(VALIDATION_PLAN["label_target"])
    coverage_ratio = round((total / label_target) * 100, 1) if label_target else 0.0

    if total >= 200:
        status_key = "growing"
        status_label = "已进入可量化分析阶段"
    elif total >= 50:
        status_key = "seed"
        status_label = "已形成初步样本池"
    else:
        status_key = "early"
        status_label = "仍处于样本积累阶段"

    return {
        "status_key": status_key,
        "status_label": status_label,
        "current_sample_count": total,
        "unique_characters": unique_characters,
        "device_count": device_count,
        "recent_sample_count": recent_total,
        "coverage_ratio": coverage_ratio,
        "label_target": label_target,
        "expert_review_target": int(VALIDATION_PLAN["expert_review_target"]),
        "trial_user_target": int(VALIDATION_PLAN["trial_user_target"]),
        "next_milestone": VALIDATION_PLAN["next_milestone"],
    }


def build_methodology_payload(summary: dict[str, Any] | None = None) -> dict[str, Any]:
    """Package framework, references, and validation context for cloud clients."""

    return {
        "framework_overview": deepcopy(FRAMEWORK_OVERVIEW),
        "dimension_basis": get_dimension_basis(),
        "authority_references": deepcopy(AUTHORITY_REFERENCES),
        "validation_plan": deepcopy(VALIDATION_PLAN),
        "validation_snapshot": build_validation_snapshot(summary),
    }
