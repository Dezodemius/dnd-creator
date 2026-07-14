import json
from pathlib import Path

import pytest

from scripts.build_lss import Coins, build_lss, CharacterDraft, modifier, proficiency_bonus, _coins_total, _skills

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = Path(__file__).parent.parent / "docs" / "Нимуэ_Плут_to_lss.json"


def _load_draft() -> CharacterDraft:
    raw = json.loads((FIXTURES / "nimue_draft.json").read_text(encoding="utf-8"))
    return CharacterDraft.model_validate(raw)


def _parse(lss: dict) -> dict:
    """Распарсить внешний JSON и вложенную строку data — сравниваем объекты, не строки."""
    parsed = dict(lss)
    parsed["data"] = json.loads(parsed["data"])
    return parsed


def _scrub(obj: dict) -> dict:
    """Убрать поля, которые заведомо не воспроизводятся детерминированной сборкой.

    - disabledBlocks._id, data.hiddenName, data.avatar, data.createdAt — случайные или
      временные значения, которые LSS-приложение (и наш build_lss) генерирует заново
      при каждом сохранении, а не хранит как данные персонажа.
    - data.text.*.size — косметическая высота текстового поля в UI LSS; в CharacterDraft
      этого понятия нет.
    - data.text.background.data, data.text.allies.data — в реальном экспорте здесь лежит
      справочный текст предыстории «Мудрец» из PHB (подставляется самим LSS при выборе
      предыстории), а не то, что несёт CharacterDraft.
    - data.text.spells-level-5.data.type — в эталонном экспорте у нетронутого блока
      5-го уровня "type": "" вместо "doc" — артефакт конкретно этого сохранения в LSS.
    """
    obj = json.loads(json.dumps(obj))
    obj["disabledBlocks"].pop("_id", None)
    data = obj["data"]
    data.pop("hiddenName", None)
    data.pop("avatar", None)
    data.pop("createdAt", None)
    for block in data.get("text", {}).values():
        block.pop("size", None)
    for key in ("background", "allies"):
        data["text"][key]["value"].pop("data", None)
    data["text"]["spells-level-5"]["value"]["data"].pop("type", None)
    return obj


def test_golden_nimue():
    """Definition of Done: сборка из руками восстановленного драфта Нимуэ совпадает с реальным экспортом."""
    draft = _load_draft()
    generated = _parse(build_lss(draft))
    golden = _parse(json.loads(GOLDEN.read_text(encoding="utf-8")))
    assert _scrub(generated) == _scrub(golden)


def test_modifier():
    assert modifier(17) == 3
    assert modifier(14) == 2
    assert modifier(10) == 0
    assert modifier(8) == -1
    assert modifier(3) == -4


@pytest.mark.parametrize(
    "level,bonus",
    [(1, 2), (4, 2), (5, 3), (8, 3), (9, 4), (12, 4), (13, 5), (16, 5), (17, 6), (20, 6)],
)
def test_proficiency_bonus(level, bonus):
    assert proficiency_bonus(level) == bonus


def test_coins_total():
    assert _coins_total(Coins(pp=0, gp=10, ep=0, sp=0, cp=0)) == 10
    assert _coins_total(Coins(pp=1, gp=0, ep=0, sp=0, cp=0)) == 10
    assert _coins_total(Coins(pp=0, gp=0, ep=1, sp=1, cp=1)) == 0.61


def test_skills_layout():
    layout = _skills({"stealth": "expert", "arcana": "proficient"})
    assert len(layout) == 18
    assert layout["stealth"]["isProf"] == 2
    assert layout["arcana"]["isProf"] == 1
    assert layout["athletics"]["isProf"] == 0
    assert layout["stealth"]["baseStat"] == "dex"
    assert layout["stealth"]["label"] == "Скрытность"
