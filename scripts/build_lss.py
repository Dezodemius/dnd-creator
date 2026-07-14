"""Шаг 2 конвейера: детерминированная сборка LSS JSON из CharacterDraft.

LLM понимает смысл и выдаёт CharacterDraft (см. docs/lss_step1_extract_prompt.md).
Всё, на чём модель ошибается тихо — модификаторы, бонус мастерства, СЛ и бонус
атаки заклинаний, раскладка 18 навыков и 6 спасбросков, LSS-обёртки и
ProseMirror-документы — считает этот файл.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

Ability = Literal["str", "dex", "con", "int", "wis", "cha"]
SkillRank = Literal["proficient", "expert"]


class Abilities(BaseModel):
    strength: int = Field(alias="str")
    dex: int
    con: int
    intelligence: int = Field(alias="int")
    wis: int
    cha: int


class Spell(BaseModel):
    name: str
    name_en: str | None
    level: int
    url: str | None


class Weapon(BaseModel):
    name: str
    damage: str
    ability: Literal["str", "dex"]
    proficient: bool


class Feature(BaseModel):
    source: Literal["class", "race", "background", "feat"]
    name: str
    text: str


class Coins(BaseModel):
    pp: int
    gp: int
    ep: int
    sp: int
    cp: int


class Proficiencies(BaseModel):
    languages: list[str]
    armor: list[str]
    weapons: list[str]
    tools: list[str]


class CharacterDraft(BaseModel):
    """Плоский семантический лист. Ничего производного, ничего LSS-специфичного."""

    name: str
    player_name: str | None
    class_name: str
    subclass: str | None
    level: int
    race: str
    background: str
    alignment: str
    experience: int

    age: int | None
    height: int | None
    weight: int | None

    abilities: Abilities
    saving_throws: list[Ability]
    skills: dict[str, SkillRank]

    hp_max: int
    hp_current: int
    hp_temp: int
    hit_die: str
    armor_class: int
    speed: int

    spellcasting_ability: Ability | None
    spell_slots: dict[str, int]
    spells: list[Spell]

    weapons: list[Weapon]
    equipment: list[str]
    coins: Coins

    personality: str | None
    ideals: str | None
    bonds: str | None
    flaws: str | None
    backstory: str | None

    features: list[Feature]
    proficiencies: Proficiencies

    attack_notes: str | None
    avatar_url: str | None


# --- константы формата -------------------------------------------------

ABILITY_ATTR = {
    "str": "strength",
    "dex": "dex",
    "con": "con",
    "int": "intelligence",
    "wis": "wis",
    "cha": "cha",
}
ABILITY_LABELS = {
    "str": "Сила",
    "dex": "Ловкость",
    "con": "Телосложение",
    "int": "Интеллект",
    "wis": "Мудрость",
    "cha": "Харизма",
}
ABILITIES_ORDER: list[Ability] = ["str", "dex", "con", "int", "wis", "cha"]

# (ключ, базовая характеристика, подпись) — порядок и подписи как в LSS
SKILLS: list[tuple[str, Ability, str]] = [
    ("acrobatics", "dex", "Акробатика"),
    ("investigation", "int", "Анализ"),
    ("athletics", "str", "Атлетика"),
    ("perception", "wis", "Восприятие"),
    ("survival", "wis", "Выживание"),
    ("performance", "cha", "Выступление"),
    ("intimidation", "cha", "Запугивание"),
    ("history", "int", "История"),
    ("sleight of hand", "dex", "Ловкость рук"),
    ("arcana", "int", "Магия"),
    ("medicine", "wis", "Медицина"),
    ("deception", "cha", "Обман"),
    ("nature", "int", "Природа"),
    ("insight", "wis", "Проницательность"),
    ("religion", "int", "Религия"),
    ("stealth", "dex", "Скрытность"),
    ("persuasion", "cha", "Убеждение"),
    ("animal handling", "wis", "Уход за животными"),
]


def ability_score(abilities: Abilities, key: Ability) -> int:
    return getattr(abilities, ABILITY_ATTR[key])


def modifier(score: int) -> int:
    return (score - 10) // 2


def proficiency_bonus(level: int) -> int:
    return 2 + (level - 1) // 4


# --- текстовые блоки -----------------------------------------------------


def _feature_html(feature: Feature) -> str:
    return f"<p><strong>{feature.name}:</strong> {feature.text}</p>"


def _traits_html(features: list[Feature]) -> str:
    class_features = [f for f in features if f.source == "class"]
    return "".join(
        f"<p><strong>{f.name}:</strong> (Полный текст в разделе 'Заметки') </p>"
        for f in class_features
    )


def _class_notes(features: list[Feature]) -> list[str]:
    """notes-1..3: умения класса, не более трёх умений на блок."""
    class_features = [f for f in features if f.source == "class"]
    chunks = [class_features[i : i + 3] for i in range(0, len(class_features), 3)]
    chunks = chunks[:3] + [[]] * max(0, 3 - len(chunks))
    blocks = []
    for chunk in chunks[:3]:
        if not chunk:
            blocks.append("")
            continue
        content = "".join(_feature_html(f) for f in chunk)
        blocks.append(f"<strong>Умения от класса:</strong> {content}")
    return blocks


def _race_note(features: list[Feature]) -> str:
    race_features = [f for f in features if f.source == "race"]
    content = "".join(_feature_html(f) for f in race_features) if race_features else "Нет"
    return f"<p><strong>Умения от расы:</strong> {content}</p>"


def _feat_note(features: list[Feature]) -> str:
    feat_features = [f for f in features if f.source == "feat"]
    content = "".join(_feature_html(f) for f in feat_features) if feat_features else "Нет"
    return f"<p><strong>Умения от черт:</strong> {content}</p>"


def _background_features_doc(features: list[Feature]) -> dict:
    background_features = [f for f in features if f.source == "background"]
    if not background_features:
        return {"type": "doc", "content": None}
    content = []
    for f in background_features:
        content.append(_pm_paragraph(f"{f.name}:"))
        content.append(_pm_paragraph(f.text))
    return {"type": "doc", "content": content}


def _prof_html(prof: Proficiencies) -> str:
    def join(values: list[str]) -> str:
        return ", ".join(values) if values else "Нет"

    return (
        f"<p><strong>Знание языков:</strong> {join(prof.languages)}</p>"
        f"<p><strong>Сопротивление к:</strong> Нет</p>"
        f"<p><strong>Доспехи:</strong> {join(prof.armor)}</p>"
        f"<p><strong>Оружие:</strong> {join(prof.weapons)}</p>"
        f"<p><strong>Инструменты от класса: </strong> {join(prof.tools)}</p>"
        f"<p><strong>Инструменты от предыстории: </strong> Нет</p>"
    )


# --- ProseMirror-документы -------------------------------------------------


def _pm_paragraph(text: str) -> dict:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def _pm_link_paragraph(text: str, url: str | None, class_name: str) -> dict:
    node: dict = {"type": "text", "text": text}
    if url:
        node["marks"] = [
            {"type": "link", "attrs": {"href": url, "target": "_blank", "class": class_name}}
        ]
    return {"type": "paragraph", "content": [node]}


def _spells_doc(spells: list[Spell], level: int, class_name: str) -> dict:
    matched = [s for s in spells if s.level == level]
    if not matched:
        return {"type": "doc", "content": None}
    content = []
    for s in matched:
        label = f"{s.name} [{s.name_en}]" if s.name_en else s.name
        content.append(_pm_link_paragraph(label, s.url, class_name))
    return {"type": "doc", "content": content}


def _equipment_doc(equipment: list[str]) -> dict:
    if not equipment:
        return {"type": "doc", "content": None}
    return {"type": "doc", "content": [_pm_paragraph(item) for item in equipment]}


def _attacks_doc(attack_notes: str | None) -> dict:
    if not attack_notes:
        return {"type": "doc", "content": None}
    return {"type": "doc", "content": [_pm_paragraph(attack_notes)]}


# --- числовые блоки ----------------------------------------------------


def _stats(abilities: Abilities) -> dict:
    return {
        key: {
            "name": key,
            "label": ABILITY_LABELS[key],
            "score": ability_score(abilities, key),
            "modifier": modifier(ability_score(abilities, key)),
            "check": 0,
        }
        for key in ABILITIES_ORDER
    }


def _saves(saving_throws: list[Ability]) -> dict:
    return {
        key: {"name": key, "isProf": key in saving_throws, "bonus": 0} for key in ABILITIES_ORDER
    }


def _skills(skills: dict[str, SkillRank]) -> dict:
    rank_value = {"proficient": 1, "expert": 2}
    return {
        key: {
            "baseStat": base_stat,
            "name": key,
            "label": label,
            "isProf": rank_value.get(skills.get(key), 0),
        }
        for key, base_stat, label in SKILLS
    }


def _coins_total(coins: Coins) -> int | float:
    total = coins.pp * 10 + coins.gp + coins.ep * 0.5 + coins.sp * 0.1 + coins.cp * 0.01
    total = round(total, 2)
    return int(total) if total == int(total) else total


def _random_id(length: int = 24) -> str:
    return "".join(random.choice("0123456789abcdef") for _ in range(length))


# --- сборка --------------------------------------------------------------


def build_character_data(draft: CharacterDraft) -> dict:
    abilities = draft.abilities
    prof_bonus = proficiency_bonus(draft.level)
    is_caster = draft.spellcasting_ability is not None
    spell_mod = (
        modifier(ability_score(abilities, draft.spellcasting_ability)) if is_caster else 0
    )
    save_dc = 8 + prof_bonus + spell_mod if is_caster else 0
    attack_bonus = prof_bonus + spell_mod if is_caster else 0

    features = draft.features
    class_notes = _class_notes(features)

    return {
        "isDefault": True,
        "jsonType": "character",
        "template": "default",
        "name": {"value": draft.name},
        "info": {
            "charClass": {"name": "charClass", "label": "класс и уровень", "value": draft.class_name},
            "level": {"name": "level", "label": "уровень", "value": draft.level},
            "background": {"name": "background", "label": "предыстория", "value": draft.background},
            "playerName": {"name": "playerName", "label": "имя игрока", "value": draft.player_name or ""},
            "race": {"name": "race", "label": "раса", "value": draft.race},
            "alignment": {"name": "alignment", "label": "мировоззрение", "value": draft.alignment},
            "experience": {"name": "experience", "label": "опыт", "value": draft.experience},
        },
        "subInfo": {
            "age": {"name": "age", "label": "возраст", "value": draft.age},
            "height": {"name": "height", "label": "рост", "value": draft.height},
            "weight": {"name": "weight", "label": "вес", "value": draft.weight},
            "eyes": {"name": "", "label": "", "value": ""},
            "skin": {"name": "", "label": "", "value": ""},
            "hair": {"name": "", "label": "", "value": ""},
        },
        "spellsInfo": {
            "base": {
                "name": "base",
                "label": "Базовая характеристика заклинаний",
                "value": "",
                "code": draft.spellcasting_ability or "",
            },
            "save": {
                "name": "save",
                "label": "Сложность спасброска",
                "value": "",
                "customModifier": str(save_dc) if is_caster else "",
            },
            "mod": {
                "name": "mod",
                "label": "Бонус атаки заклинанием",
                "value": "",
                "customModifier": str(attack_bonus) if is_caster else "",
            },
        },
        "spells": {f"slots-{lvl}": {"value": count} for lvl, count in draft.spell_slots.items()},
        "spellsPact": {},
        "proficiency": prof_bonus,
        "stats": _stats(abilities),
        "saves": _saves(draft.saving_throws),
        "skills": _skills(draft.skills),
        "vitality": {
            "hp-dice-current": {"value": draft.level},
            "hp-dice-multi": {},
            "hp-max": {"value": draft.hp_max},
            "hp-current": {"value": draft.hp_current},
            "hp-temp": {"value": draft.hp_temp},
            "isDying": False,
            "deathFails": 0,
            "deathSuccesses": 0,
            "ac": {"value": draft.armor_class},
            "speed": {"value": draft.speed},
            "hit-die": {"value": draft.hit_die},
            "hp-max-bonus": {"value": 0},
        },
        "weaponsList": [
            {
                "id": "",
                "name": {"value": w.name},
                "mod": {"value": ""},
                "dmg": {"value": w.damage},
                "isProf": w.proficient,
                "ability": w.ability,
                "modBonus": {"value": 0},
                "modCustom": {"value": 0},
            }
            for w in draft.weapons
        ],
        "weapons": {},
        "text": {
            "traits": {"value": {"data": _traits_html(features)}},
            "attacks": {"value": {"data": _attacks_doc(draft.attack_notes)}},
            **{
                f"spells-level-{lvl}": {
                    "value": {"data": _spells_doc(draft.spells, lvl, draft.class_name)}
                }
                for lvl in range(6)
            },
            "equipment": {"value": {"data": _equipment_doc(draft.equipment)}, "isHidden": False},
            "background": {"value": {"data": draft.backstory or ""}},
            "ideals": {"value": {"data": draft.ideals or ""}},
            "personality": {"value": {"data": draft.personality or ""}},
            "flaws": {"value": {"data": draft.flaws or ""}},
            "bonds": {"value": {"data": draft.bonds or ""}},
            "allies": {"value": {"data": ""}},
            "quests": {"value": {"data": ""}},
            "prof": {"value": {"data": _prof_html(draft.proficiencies)}},
            "notes-1": {"value": {"data": class_notes[0]}},
            "notes-2": {"value": {"data": class_notes[1]}},
            "notes-3": {"value": {"data": class_notes[2]}},
            "notes-4": {"value": {"data": _race_note(features)}},
            "notes-5": {"value": {"data": _feat_note(features)}},
            "notes-6": {"value": {"data": ""}},
            "features": {"value": {"data": _background_features_doc(features)}},
            "items": {"value": {"data": ""}},
        },
        "coins": {
            "gp": {"value": draft.coins.gp},
            "total": {"value": _coins_total(draft.coins)},
            "sp": {"value": draft.coins.sp},
            "cp": {"value": draft.coins.cp},
            "pp": {"value": draft.coins.pp},
            "ep": {"value": draft.coins.ep},
        },
        "resources": {},
        "bonusesSkills": None,
        "bonusesStats": None,
        "conditions": None,
        "hiddenName": draft.name,
        "casterClass": {"value": draft.class_name},
        "avatar": {"jpeg": draft.avatar_url or "", "webp": draft.avatar_url or ""},
        "inspiration": False,
        "exhaustion": "",
        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "proficiencyCustom": 0,
    }


def build_lss(draft: CharacterDraft) -> dict:
    return {
        "tags": [],
        "disabledBlocks": {
            "info-left": [],
            "info-right": [],
            "notes-left": [],
            "notes-right": [],
            "_id": _random_id(),
        },
        "spells": {"mode": "text", "prepared": [], "book": []},
        "data": json.dumps(build_character_data(draft), ensure_ascii=False),
        "edition": "2014",
        "jsonType": "character",
        "version": "2",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Собрать LSS JSON из CharacterDraft")
    parser.add_argument("draft", help="путь к JSON-файлу CharacterDraft")
    parser.add_argument("-o", "--output", help="куда сохранить LSS JSON (по умолчанию — stdout)")
    args = parser.parse_args()

    with open(args.draft, encoding="utf-8") as f:
        raw = json.load(f)

    try:
        draft = CharacterDraft.model_validate(raw)
    except ValidationError as exc:
        print(f"draft.json не прошёл валидацию:\n{exc}", file=sys.stderr)
        sys.exit(1)

    output = json.dumps(build_lss(draft), ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
