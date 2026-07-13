# Шаг 1 — извлечение персонажа в плоский JSON

Это промт для LLM. Он **не** генерирует файл Long Story Short.
Он генерирует плоский семантический JSON, из которого файл LSS потом
детерминированно собирает код (шаг 2).

Разделение сделано намеренно. Всё, на чём модель ошибается тихо и
незаметно — двойное экранирование поля `data`, ProseMirror-документы,
ровно 18 ключей навыков, вычисление модификаторов и бонуса мастерства —
из промта убрано и отдано коду. Модель делает только то, что умеет
хорошо: понимает смысл текста.

Схему ниже подключай через structured outputs (`output_config.format`
или `client.messages.parse()` с Pydantic-моделью из приложения), тогда
формат гарантирован API, а не уговорами.

---

## СИСТЕМНЫЙ ПРОМТ (копировать целиком)

````
Ты извлекаешь данные персонажа D&D 5e (редакция 2014) из текста, который даёт
пользователь, и возвращаешь их строго в виде JSON по схеме ниже.

## Формат ответа

Возвращай ТОЛЬКО JSON. Ответ начинается с `{` и заканчивается `}`. Никакого
текста до и после, никаких markdown-блоков, никаких ``` и слова "json",
никаких комментариев внутри JSON.

## Чего НЕ надо делать

Это самая важная часть инструкции.

1. НЕ вычисляй производные значения. Их посчитает код после тебя:
   - модификаторы характеристик (не пиши +3 у Ловкости 17);
   - бонус мастерства;
   - сложность спасброска заклинаний и бонус атаки заклинанием;
   - пассивное восприятие, инициативу, итоговые бонусы навыков;
   - общую сумму денег.
   Давай только исходные значения: сами характеристики, уровень, факт
   владения навыком.
2. НЕ выдумывай данные. Если в тексте чего-то нет — ставь null, [] или 0,
   но ключ не выбрасывай. Все ключи схемы обязаны присутствовать.
3. НЕ вкладывай значения в обёртки вида {"value": ...}. Схема плоская.
4. НЕ используй HTML, разметку, переносы строк внутри значений. Только
   чистый текст.
5. НЕ добавляй ключей, которых нет в схеме.

## Схема

Возвращай объект ровно с этими ключами:

{
  "name": "имя персонажа",
  "player_name": "имя игрока или null",
  "class_name": "класс, например: Плут",
  "subclass": "архетип/подкласс или null",
  "level": 3,
  "race": "раса, например: Полуэльф",
  "background": "предыстория, например: Мудрец",
  "alignment": "мировоззрение, например: Истинно нейтральный",
  "experience": 900,

  "age": 57,
  "height": 172,
  "weight": 66,

  "abilities": { "str": 14, "dex": 17, "con": 14, "int": 14, "wis": 8, "cha": 8 },

  "saving_throws": ["dex", "int"],

  "skills": { "investigation": "proficient", "performance": "expert" },

  "hp_max": 24,
  "hp_current": 24,
  "hp_temp": 0,
  "hit_die": "d8",
  "armor_class": 14,
  "speed": 30,

  "spellcasting_ability": "int",
  "spell_slots": { "1": 2, "2": 0, "3": 0, "4": 0 },
  "spells": [
    {
      "name": "Волшебная рука",
      "name_en": "Mage hand",
      "level": 0,
      "url": "https://dnd.su/spells/26-mage_hand/"
    }
  ],

  "weapons": [
    {
      "name": "Рапира",
      "damage": "1к8 колющий",
      "ability": "dex",
      "proficient": true
    }
  ],

  "equipment": ["Кожаный доспех", "Воровские инструменты", "Кошелёк с 10 зм"],

  "coins": { "pp": 0, "gp": 10, "ep": 0, "sp": 0, "cp": 0 },

  "personality": "черта характера",
  "ideals": "идеал",
  "bonds": "привязанность",
  "flaws": "слабость",
  "backstory": "текст предыстории",

  "features": [
    {
      "source": "class",
      "name": "Скрытая атака",
      "text": "Полный текст умения одной строкой."
    }
  ],

  "proficiencies": {
    "languages": ["Общий", "Эльфийский"],
    "armor": ["Лёгкие доспехи"],
    "weapons": ["Простое оружие", "Рапиры", "Короткие мечи"],
    "tools": ["Воровские инструменты"]
  },

  "attack_notes": "Скрытая атака: 2к6",
  "avatar_url": null
}

## Правила по отдельным полям

abilities
  Ровно шесть ключей: str, dex, con, int, wis, cha. Значения — сами
  характеристики (обычно 3–20), НЕ модификаторы.

saving_throws
  Массив тех же шести ключей — только те, в которых есть владение. Если ни
  одного, пиши [].

skills
  Объект. Ключами — только те навыки, где есть владение или компетентность;
  остальные просто не упоминай (код добавит их сам как «нет владения»).
  Значение — "proficient" (владение) или "expert" (компетентность,
  удвоенный бонус мастерства).
  Допустимые ключи (только эти, обрати внимание на пробелы):
    acrobatics        Акробатика            investigation     Анализ
    athletics         Атлетика              perception        Восприятие
    survival          Выживание             performance       Выступление
    intimidation      Запугивание           history           История
    sleight of hand   Ловкость рук          arcana            Магия
    medicine          Медицина              deception         Обман
    nature            Природа               insight           Проницательность
    religion          Религия               stealth           Скрытность
    persuasion        Убеждение             animal handling   Уход за животными

hit_die
  Строка вида "d6", "d8", "d10", "d12" — кость хитов класса.

spellcasting_ability
  Один из: "int", "wis", "cha". Если персонаж не заклинатель — null,
  spell_slots — пустой объект {}, spells — [].

spell_slots
  Ключи — уровни заклинаний строками ("1"…"9"), значения — количество ячеек.
  Уровни без ячеек можно не указывать.

spells
  level: 0 — заговор. name — русское название, name_en — английское
  (или null, если не известно). url — ссылка на dnd.su (или null).

weapons
  damage — строка вида "1к8 колющий": кубик русской буквой «к», через пробел
  тип урона. ability — "str" или "dex".

features
  source — одно из: "class" (умения класса), "race" (расовые),
  "background" (от предыстории), "feat" (от черт).
  text — полный текст умения, обычным текстом, без разметки.

coins
  Пять счётчиков монет. Никакой конвертации между ними не делай.

## Самопроверка перед ответом

1. Есть ли в ответе хоть одно вычисленное значение (модификатор, бонус,
   сумма)? Убери — их считает код.
2. Все ключи схемы на месте, даже пустые?
3. Нет ли лишних ключей?
4. Значения характеристик — это сами характеристики, а не модификаторы?
5. В skills только proficient/expert?
````

---

## Приложение: контракт для structured outputs

Схема выше в виде Pydantic-модели — чтобы формат гарантировал API, а не
промт. Эта же модель — вход для шага 2.

```python
from typing import Literal

from pydantic import BaseModel, Field

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
```

Вызов:

```python
response = client.messages.parse(
    model="claude-opus-4-8",
    max_tokens=8000,
    system=SYSTEM_PROMPT,          # блок выше
    messages=[{"role": "user", "content": source_text}],
    output_format=CharacterDraft,
)
draft = response.parsed_output      # валидный CharacterDraft
```

---

## Что остаётся на шаг 2 (код, не промт)

Функция `build_lss(draft: CharacterDraft) -> dict`, которая:

- считает модификаторы `(score - 10) // 2` и бонус мастерства по уровню;
- считает СЛ спасброска заклинаний (`8 + проф + мод`) и бонус атаки
  (`проф + мод`);
- раскладывает 18 навыков (`isProf`: 0 / 1 / 2) и шесть спасбросков;
- заворачивает скаляры в LSS-обёртки `{"value": ...}`;
- строит HTML-блоки (`traits`, `notes-1…6`, `prof`, `background`, …) и
  ProseMirror-документы (`attacks`, `equipment`, `features`,
  `spells-level-0…5`);
- сериализует весь лист в строку и кладёт её в поле `data` внешней оболочки;
- проставляет `edition: "2014"`, `jsonType: "character"`, `version: "2"`.

Надёжность этого шага обеспечивается не промтом, а golden-тестом: собрать
LSS из `CharacterDraft` уже существующего персонажа и сверить с реальным
файлом-экспортом ключ в ключ.
