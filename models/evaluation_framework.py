"""Source-backed rubric metadata for InkPi regular/running script evaluation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from config import SCRIPT_CONFIG


DEFAULT_SCRIPT = str(SCRIPT_CONFIG["default"])
SCRIPT_LABELS = dict(SCRIPT_CONFIG["labels"])
SUPPORTED_SCRIPTS = tuple(SCRIPT_CONFIG["supported"])
LEGACY_RUBRIC_VERSION = "legacy_v0"
RUBRIC_VERSION = "source_backed_rubric_v1"
RUBRIC_ANCHORS = (20, 40, 60, 80, 100)


RUBRIC_SOURCE_CATALOG = {
    "MOE-2013": {
        "code": "MOE-2013",
        "title": "中小学书法教育指导纲要",
        "organization": "教育部",
        "url": "https://www.moe.gov.cn/srcsite/A26/s8001/201301/t20130125_147389.html",
        "usage": "界定规范书写、技能训练、评价多元的教育边界，保证系统定位为辅助评测而非自动考级。",
    },
    "MOE-2025": {
        "code": "MOE-2025",
        "title": "关于 2022 课标背景下规范汉字书写学习要求的答复",
        "organization": "教育部",
        "url": "https://hudong.moe.gov.cn/jyb_xxgk/xxgk_jyta/jyta_jiaocaiju/202501/t20250113_1175495.html",
        "usage": "明确基础 progression 为楷书到规范、通行的行楷/行书，为双书体支持提供课程依据。",
    },
    "SC-SHFA-2018": {
        "code": "SC-SHFA-2018",
        "title": "四川省书法水平测试毛笔书法测试大纲",
        "organization": "四川省教育考试院",
        "url": "https://www.sceeo.com/Html/201809/Newsdetail_817.html",
        "usage": "提供笔法、字法、章法、卷面等可量化权重骨架，适合单字练习场景的初段评价。",
    },
    "CAA-EXAM-2018": {
        "code": "CAA-EXAM-2018",
        "title": "中国美术学院社会美术水平考级中心软笔书法考试与培训标准",
        "organization": "中国美术学院社会美术水平考级中心",
        "url": "https://mskj.caa.edu.cn/bkzn/kjdg/201809/33247.html",
        "usage": "补强笔法结构准确度、提按顿挫、线条力度、章法完善、点画有力等训练描述。",
    },
    "CWA-REVIEW-2024": {
        "code": "CWA-REVIEW-2024",
        "title": "中国书法家协会全国第十三届书法篆刻展评审评议",
        "organization": "中国书法家协会",
        "url": "https://www.cflac.org.cn/ys/sf/sfht/202405/t20240517_1316199.html",
        "usage": "补入笔法、结构、章法、墨法、笔力、规范识别与行草气韵贯通等比赛审美语言。",
    },
}


RUBRIC_DEFINITIONS = {
    "regular": {
        "script": "regular",
        "script_label": SCRIPT_LABELS["regular"],
        "rubric_family": "regular_rubric_v1",
        "rubric_label": "楷书正式评审标准",
        "scope_note": "仅适配毛笔楷书单字练习，不延展到整幅作品章法、落款、印章和文辞。",
        "transition_note": "当前阶段只替换正式维度层，主分 total_score 仍沿用现有 ONNX 模型输出。",
        "items": [
            {
                "key": "bifa_dianhua",
                "label": "笔法点画",
                "weight": 30,
                "basis_codes": ["SC-SHFA-2018", "CAA-EXAM-2018", "CWA-REVIEW-2024"],
                "focus": "点画起收、提按节奏、线条力度和笔势控制。",
                "anchor_texts": {
                    20: "点画失稳、提按不明，线质与笔势控制明显不足。",
                    40: "能形成基本点画，但起收笔和提按顿挫仍较生硬。",
                    60: "点画基本成形，提按较清楚，线条质量达到练习可接受水平。",
                    80: "点画准确，提按顿挫较自然，线条力度与笔势较稳定。",
                    100: "点画自然生动，起收分明，线条质量与笔势控制表现突出。",
                },
                "practice_templates": [
                    "先放慢起笔和收笔，优先把主笔写稳。",
                    "重练横竖撇捺的提按转换，减少笔画轻重失衡。",
                    "下一轮先只盯点画质量，再看整体分数。",
                ],
            },
            {
                "key": "jieti_zifa",
                "label": "结体字法",
                "weight": 30,
                "basis_codes": ["SC-SHFA-2018", "CAA-EXAM-2018", "MOE-2013"],
                "focus": "间架结构、重心、比例关系和部件组织。",
                "anchor_texts": {
                    20: "结体明显失衡，重心偏移，部件比例关系难以成立。",
                    40: "字形基本可辨，但重心、比例或主次关系仍较松散。",
                    60: "结构轮廓基本成立，重心较稳，比例关系达到基础训练要求。",
                    80: "结构较严整，重心与比例协调，字法表达稳定清楚。",
                    100: "结体端正而有法度，比例精当，间架安排具有成熟度。",
                },
                "practice_templates": [
                    "先看中宫和主笔位置，再决定左右与上下留白。",
                    "下一轮把最容易偏斜的部件单独练两次后再整字复测。",
                    "保持当前字形比例，不要同时大改所有部件。",
                ],
            },
            {
                "key": "bubai_zhangfa",
                "label": "布白章法",
                "weight": 15,
                "basis_codes": ["SC-SHFA-2018", "CWA-REVIEW-2024"],
                "focus": "单字内部布白、主次层次与视觉节奏，不扩展到整幅作品章法。",
                "anchor_texts": {
                    20: "布白紊乱，主体挤压或散乱，单字内部章法关系失衡。",
                    40: "有基本布白意识，但主次层次和空间节奏仍不够清楚。",
                    60: "单字内部留白较合理，主次关系基本明确。",
                    80: "布白较匀整，空间节奏清晰，主次关系表达稳定。",
                    100: "布白有分寸感，单字内部章法完整且具有较好节奏感。",
                },
                "practice_templates": [
                    "拍照前先看主体是否居中，避免单字挤到边缘。",
                    "下一轮优先整理左右和上下留白，再微调细节。",
                    "保持单字主体集中，减少背景和杂笔干扰。",
                ],
            },
            {
                "key": "mofa_bili",
                "label": "墨法笔力",
                "weight": 15,
                "basis_codes": ["CAA-EXAM-2018", "CWA-REVIEW-2024"],
                "focus": "墨色层次、线质力度与整体笔力表现。",
                "anchor_texts": {
                    20: "墨气与笔力都较弱，线条发飘或发虚，难以支撑字势。",
                    40: "能看到基础墨色变化，但力度控制仍不够稳定。",
                    60: "墨色和笔力表现达到基础训练要求，线质较清楚。",
                    80: "墨气较足，线条有力度，整体笔力与质感较稳定。",
                    100: "墨气、笔力和线质表现成熟，整体具有较强精神气象。",
                },
                "practice_templates": [
                    "保持运笔速度一致，避免墨色忽轻忽重。",
                    "先稳住主笔力度，再观察整字的墨气是否连贯。",
                    "下一轮保持同样的落笔节奏，减少末笔发虚。",
                ],
            },
            {
                "key": "guifan_wanzheng",
                "label": "规范完整",
                "weight": 10,
                "basis_codes": ["MOE-2013", "SC-SHFA-2018", "CWA-REVIEW-2024"],
                "focus": "规范书写、主体完整、识别清晰与拍摄/输出完整性。",
                "anchor_texts": {
                    20: "存在明显缺笔、错形或主体残缺，规范识别较差。",
                    40: "主体可辨，但仍有缺笔、碰边或规范性不足的问题。",
                    60: "主体基本完整，识别较稳定，规范性达到基础要求。",
                    80: "主体完整清晰，规范性较好，识别与展示都较稳定。",
                    100: "主体完整且规范，识别清楚，适合作为阶段性展示样张。",
                },
                "practice_templates": [
                    "先保证单字完整入框，再追求更高分数。",
                    "下一轮重点检查是否缺笔、断笔或主体碰边。",
                    "保持拍摄与书写姿态稳定，优先提升识别清晰度。",
                ],
            },
        ],
    },
    "running": {
        "script": "running",
        "script_label": SCRIPT_LABELS["running"],
        "rubric_family": "running_rubric_v1",
        "rubric_label": "行书正式评审标准",
        "scope_note": "仅适配毛笔行书单字练习，不扩展到整幅作品章法与文本内容评价。",
        "transition_note": "当前阶段只替换正式维度层，主分 total_score 仍沿用现有 ONNX 模型输出。",
        "items": [
            {
                "key": "yongbi_xianzhi",
                "label": "用笔线质",
                "weight": 25,
                "basis_codes": ["CAA-EXAM-2018", "CWA-REVIEW-2024"],
                "focus": "提按顿挫、线条力度、用笔控制与线质表现。",
                "anchor_texts": {
                    20: "线条发飘、发虚或失控，用笔质量不足以支撑行书节奏。",
                    40: "能看到基本线条变化，但提按与线质仍较粗疏。",
                    60: "线质达到基础训练要求，用笔控制开始稳定。",
                    80: "线质清楚，提按与转折较自然，用笔较见精神。",
                    100: "线质成熟而有表现力，用笔控制与节奏高度统一。",
                },
                "practice_templates": [
                    "先把主线条写顺，再去追求连带和速度。",
                    "下一轮重点观察线条是否发飘，减少虚笔和抖动。",
                    "保持同一速度写完主笔，别在中途频繁改力道。",
                ],
            },
            {
                "key": "jieti_qushi",
                "label": "结体取势",
                "weight": 20,
                "basis_codes": ["MOE-2025", "CWA-REVIEW-2024"],
                "focus": "行书中的结体组织、取势方向和整体重心。",
                "anchor_texts": {
                    20: "取势杂乱，重心失衡，结构无法稳定支撑行书书写。",
                    40: "可见基本取势，但结构与重心关系仍不够清晰。",
                    60: "结构基本稳定，取势关系达到基础练习要求。",
                    80: "结体与取势较协调，既有流动感又不失整体控制。",
                    100: "结体与取势成熟统一，行书动态与重心控制表现突出。",
                },
                "practice_templates": [
                    "下一轮先稳住重心，再决定字势往哪边走。",
                    "不要一味追求斜势，先让结构站得住。",
                    "保持当前顺势方向，只微调最容易失衡的部件。",
                ],
            },
            {
                "key": "liandai_jiezou",
                "label": "连带节奏",
                "weight": 25,
                "basis_codes": ["MOE-2025", "CWA-REVIEW-2024"],
                "focus": "行书连带关系、书写节奏和气脉贯通。",
                "anchor_texts": {
                    20: "连带关系混乱，节奏断裂，难以形成行书气脉。",
                    40: "有连带尝试，但节奏仍显生硬或时断时续。",
                    60: "连带与节奏基本可辨，行书气息开始建立。",
                    80: "连带自然，节奏较稳，气脉贯通感较清楚。",
                    100: "连带与节奏高度统一，行书流动性与气韵表现突出。",
                },
                "practice_templates": [
                    "先让连带自然出现，不要为了连而连。",
                    "下一轮连续写三次同一字，观察节奏是否一致。",
                    "保持一口气写完主线，减少中途停顿。",
                ],
            },
            {
                "key": "moqi_bili",
                "label": "墨气笔力",
                "weight": 20,
                "basis_codes": ["CAA-EXAM-2018", "CWA-REVIEW-2024"],
                "focus": "行书中的墨气流动、笔力表现与整体精神气息。",
                "anchor_texts": {
                    20: "墨气与笔力明显不足，字势松散，精神性较弱。",
                    40: "能看到基础墨气和力度，但整体气息仍不够连贯。",
                    60: "墨气与笔力达到基础练习要求，整体气息基本成立。",
                    80: "墨气与笔力较统一，行书的流动精神感较稳定。",
                    100: "墨气充足、笔力充盈，整体气息连贯且有表现力。",
                },
                "practice_templates": [
                    "保持一轮内的墨色和运笔速度一致。",
                    "先稳住主笔力度，避免越写越虚。",
                    "下一轮观察整字是否有一口气写成的感觉。",
                ],
            },
            {
                "key": "guifan_shibie",
                "label": "规范识别",
                "weight": 10,
                "basis_codes": ["MOE-2013", "MOE-2025", "CWA-REVIEW-2024"],
                "focus": "在行书流动性下保持规范边界、主体完整和稳定识别。",
                "anchor_texts": {
                    20: "连带过度或主体残缺，规范识别明显不足。",
                    40: "主体基本可辨，但规范性和完整度仍不稳定。",
                    60: "识别与规范性达到基础要求，可作为练习记录。",
                    80: "识别较稳定，规范边界清楚，适合持续量化跟踪。",
                    100: "既保持行书流动性，又能稳定识别并维持规范边界。",
                },
                "practice_templates": [
                    "优先保证主体可辨，再去追求更强流动感。",
                    "下一轮重点检查是否碰边、缺笔或过度连带。",
                    "保持拍摄和书写方式一致，让识别结果更稳定。",
                ],
            },
        ],
    },
}


FRAMEWORK_OVERVIEW = {
    "project_position": "面向毛笔楷书与行书单字练习的辅助评测系统，强调训练反馈，不替代教师终评与正式考级。",
    "current_scope": "当前正式支持楷书与行书单字；隶书、草书、篆书及多字作品不在当前支持范围内。",
    "boundary_note": "比赛与协会中的整幅章法、落款、印章和文辞要求不纳入当前单字产品评分。",
    "target_users": ["初学者", "课堂训练", "设备端即时反馈", "教师辅助点评"],
    "current_scripts": [SCRIPT_LABELS[key] for key in SUPPORTED_SCRIPTS],
    "unsupported_scripts": list(SCRIPT_CONFIG["unsupported_labels"]),
    "transition_policy": "新标准先替换维度层与方法论层，当前 formal total_score 暂不切换。",
}


VALIDATION_PLAN = {
    "current_stage": "Stage 2 / 来源化五维标准已接入，主分仍为旧模型输出",
    "next_milestone": "完成按新 rubric 的双书体人工标注与专家复核后，再切换正式主分。",
    "label_target": 500,
    "expert_review_target": 3,
    "trial_user_target": 20,
    "manual_review_policy": [
        "当前正式展示采用来源化五维标准，但 total_score 仍沿用现有模型输出。",
        "新标准训练前，保留人工评分与系统评分对照，不把 rubric_preview_total 当正式主分。",
        "优先收集楷书与行书单字样本，并记录设备来源、时间分布和专家复核意见。",
    ],
}


def normalize_script(script: str | None) -> str:
    candidate = str(script or DEFAULT_SCRIPT).strip().lower()
    return candidate if candidate in SUPPORTED_SCRIPTS else DEFAULT_SCRIPT


def get_script_label(script: str | None) -> str:
    return SCRIPT_LABELS[normalize_script(script)]


def get_rubric_definition(script: str | None) -> dict[str, Any]:
    return deepcopy(RUBRIC_DEFINITIONS[normalize_script(script)])


def get_rubric_source_catalog(codes: list[str] | tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    if not codes:
        ordered_codes = list(RUBRIC_SOURCE_CATALOG.keys())
    else:
        ordered_codes = []
        for code in codes:
            if code in RUBRIC_SOURCE_CATALOG and code not in ordered_codes:
                ordered_codes.append(code)
    return [deepcopy(RUBRIC_SOURCE_CATALOG[code]) for code in ordered_codes]


def summarize_rubric_items(rubric_items: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]] | None:
    if not rubric_items:
        return None
    ranked = [
        item
        for item in rubric_items
        if item.get("score") is not None
    ]
    if not ranked:
        return None
    best = max(ranked, key=lambda item: (int(item["score"]), -ranked.index(item)))
    weakest = min(ranked, key=lambda item: (int(item["score"]), ranked.index(item)))
    return {
        "best": {
            "key": best["key"],
            "label": best["label"],
            "score": int(best["score"]),
        },
        "weakest": {
            "key": weakest["key"],
            "label": weakest["label"],
            "score": int(weakest["score"]),
        },
    }


def build_rubric_items(
    rubric_scores: dict[str, int] | None,
    *,
    script: str | None,
) -> list[dict[str, Any]]:
    if not rubric_scores:
        return []

    definition = get_rubric_definition(script)
    rubric_items: list[dict[str, Any]] = []
    for item_def in definition["items"]:
        key = item_def["key"]
        if key not in rubric_scores or rubric_scores[key] is None:
            continue
        score = int(rubric_scores[key])
        basis_codes = list(item_def["basis_codes"])
        rubric_items.append(
            {
                "key": key,
                "label": item_def["label"],
                "score": score,
                "weight": int(item_def["weight"]),
                "basis_codes": basis_codes,
                "basis_labels": [RUBRIC_SOURCE_CATALOG[code]["title"] for code in basis_codes],
                "focus": item_def["focus"],
                "evidence_summary": item_def["anchor_texts"].get(score, item_def["anchor_texts"][60]),
                "anchor_descriptions": deepcopy(item_def["anchor_texts"]),
                "practice_templates": list(item_def["practice_templates"]),
            }
        )
    return rubric_items


def build_rubric_preview_total(rubric_items: list[dict[str, Any]] | None) -> float | None:
    if not rubric_items:
        return None
    total_weight = sum(int(item.get("weight", 0)) for item in rubric_items)
    if total_weight <= 0:
        return None
    weighted = sum(int(item["score"]) * int(item["weight"]) for item in rubric_items)
    return round(weighted / total_weight, 1)


def build_scope_boundary(script: str | None = None) -> dict[str, Any]:
    normalized_script = normalize_script(script)
    definition = get_rubric_definition(normalized_script)
    return {
        "project_position": FRAMEWORK_OVERVIEW["project_position"],
        "current_scope": FRAMEWORK_OVERVIEW["current_scope"],
        "boundary_note": FRAMEWORK_OVERVIEW["boundary_note"],
        "current_scripts": deepcopy(FRAMEWORK_OVERVIEW["current_scripts"]),
        "unsupported_scripts": deepcopy(FRAMEWORK_OVERVIEW["unsupported_scripts"]),
        "transition_policy": FRAMEWORK_OVERVIEW["transition_policy"],
        "current_script": normalized_script,
        "current_script_label": definition["script_label"],
        "current_rubric_family": definition["rubric_family"],
        "scope_note": definition["scope_note"],
        "transition_note": definition["transition_note"],
    }


def build_practice_profile(
    rubric_items: list[dict[str, Any]] | None,
    *,
    total_score: int,
    quality_level: str,
    character_name: str | None = None,
    script: str | None = None,
    rubric_version: str | None = None,
) -> dict[str, Any]:
    normalized_script = normalize_script(script)
    definition = get_rubric_definition(normalized_script)
    script_label = definition["script_label"]
    effective_version = str(rubric_version or LEGACY_RUBRIC_VERSION).strip() or LEGACY_RUBRIC_VERSION

    if effective_version == LEGACY_RUBRIC_VERSION or not rubric_items:
        return {
            "stage_key": "legacy",
            "stage_label": "旧版评测标准",
            "stage_goal": "该记录仍沿用旧版四维解释结果，暂不直接映射为新标准。",
            "scope_note": build_scope_boundary(normalized_script)["boundary_note"],
            "coach_prompt": f"这条 {script_label} 记录生成于新版 rubric 接入前，建议优先查看新版评测记录进行量化比较。",
            "best_dimension": None,
            "focus_dimension": None,
            "script": normalized_script,
            "script_label": script_label,
            "rubric_family": "legacy_v0",
            "next_actions": [
                "保留这条旧记录作为历史对照，不把旧四维直接当成新标准。",
                "重新拍摄同一单字，生成一条新版 rubric 记录再做比较。",
                "后续训练和展示统一以新五维正式标准为准。",
            ],
        }

    summary = summarize_rubric_items(rubric_items) or {}
    best = summary.get("best")
    weakest = summary.get("weakest")
    weakest_item = next((item for item in rubric_items if item["key"] == weakest["key"]), None) if weakest else None
    best_item = next((item for item in rubric_items if item["key"] == best["key"]), None) if best else None

    if total_score >= 85 and quality_level == "good":
        stage_key = "refine"
        stage_label = "巩固提炼阶段"
        stage_goal = f"保持当前 {script_label} 主分稳定的同时，继续压实最弱评审项。"
    elif total_score >= 70:
        stage_key = "stabilize"
        stage_label = "收紧标准阶段"
        stage_goal = f"优先把最弱 rubric 项拉到 60 分以上，再追求更高主分。"
    else:
        stage_key = "foundation"
        stage_label = "基础回正阶段"
        stage_goal = f"先保证 {script_label} 单字完整、规范、可稳定识别，再进入下一轮提分。"

    character_text = f"“{character_name}”" if character_name else "当前单字"
    coach_prompt = (
        f"{character_text} 本轮先看 {weakest['label']}，再保留 {best['label']} 的现有优势。"
        if weakest and best
        else f"{character_text} 建议以新五维标准继续记录，形成可对比的训练轨迹。"
    )

    next_actions = list((weakest_item or {}).get("practice_templates") or [])
    if best_item is not None:
        next_actions.append(f"继续保留 {best_item['label']} 的现有写法，避免同时改动所有笔路。")
    return {
        "stage_key": stage_key,
        "stage_label": stage_label,
        "stage_goal": stage_goal,
        "scope_note": build_scope_boundary(normalized_script)["boundary_note"],
        "coach_prompt": coach_prompt,
        "script": normalized_script,
        "script_label": script_label,
        "rubric_family": definition["rubric_family"],
        "best_dimension": best_item,
        "focus_dimension": weakest_item,
        "next_actions": next_actions[:4],
    }


def build_validation_snapshot(summary: dict[str, Any] | None) -> dict[str, Any]:
    summary = summary or {}
    total = int(summary.get("total") or 0)
    unique_characters = int(summary.get("unique_characters") or 0)
    device_count = int(summary.get("device_count") or 0)
    recent_total = int(summary.get("recent_total") or 0)
    reviewed_result_count = int(summary.get("reviewed_result_count") or 0)
    review_record_count = int(summary.get("review_record_count") or 0)
    label_target = int(VALIDATION_PLAN["label_target"])
    coverage_ratio = round((total / label_target) * 100, 1) if label_target else 0.0
    review_coverage_rate = round((reviewed_result_count / total) * 100, 1) if total else 0.0

    if total >= 200 and reviewed_result_count >= 30:
        status_key = "growing"
        status_label = "已进入可量化复核阶段"
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
        "reviewed_result_count": reviewed_result_count,
        "review_record_count": review_record_count,
        "coverage_ratio": coverage_ratio,
        "review_coverage_rate": review_coverage_rate,
        "agreement_rate": summary.get("agreement_rate"),
        "average_score_gap": summary.get("average_score_gap"),
        "label_target": label_target,
        "expert_review_target": int(VALIDATION_PLAN["expert_review_target"]),
        "trial_user_target": int(VALIDATION_PLAN["trial_user_target"]),
        "next_milestone": VALIDATION_PLAN["next_milestone"],
        "supported_scripts": list(SUPPORTED_SCRIPTS),
        "supported_script_labels": deepcopy(FRAMEWORK_OVERVIEW["current_scripts"]),
    }


def build_methodology_payload(
    summary: dict[str, Any] | None = None,
    *,
    script: str | None = None,
) -> dict[str, Any]:
    normalized_script = normalize_script(script)
    definition = get_rubric_definition(normalized_script)
    all_codes: list[str] = []
    for script_definition in RUBRIC_DEFINITIONS.values():
        for item in script_definition["items"]:
            for code in item["basis_codes"]:
                if code not in all_codes:
                    all_codes.append(code)

    return {
        "framework_overview": deepcopy(FRAMEWORK_OVERVIEW),
        "rubric_definitions": {
            key: deepcopy(value) for key, value in RUBRIC_DEFINITIONS.items()
        },
        "rubric_source_catalog": get_rubric_source_catalog(all_codes),
        "validation_plan": deepcopy(VALIDATION_PLAN),
        "validation_snapshot": build_validation_snapshot(summary),
        "supported_scripts": list(SUPPORTED_SCRIPTS),
        "supported_script_labels": [
            {"key": key, "label": SCRIPT_LABELS[key]} for key in SUPPORTED_SCRIPTS
        ],
        "current_script_scope": {
            "script": normalized_script,
            "script_label": definition["script_label"],
            "rubric_family": definition["rubric_family"],
            "rubric_label": definition["rubric_label"],
            "scope_note": definition["scope_note"],
            "transition_note": definition["transition_note"],
        },
    }
