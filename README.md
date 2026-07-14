# dnd-creator

Хранилище персонажей D&D 5e (редакция 2014) для одного мастера. Мастер
вставляет анкету игрока или готового персонажа в форму — дальше персонаж
собирается автоматически и попадает в этот репозиторий.

## Как устроен конвейер

```
index.html (форма) → inbox/*.md → generate.yml (Claude) → characters/<slug>/
                                        │
                                        └─ scripts/build_lss.py собирает LSS-файл
```

1. Форма на GitHub Pages кладёт анкету в `inbox/` через GitHub Contents API.
2. Push в `inbox/**` запускает `.github/workflows/generate.yml`.
3. Claude (по инструкции `.github/prompts/generate.md`) при необходимости
   придумывает персонажа (`.claude/skills/character-generator`), извлекает
   плоский `CharacterDraft`, а `scripts/build_lss.py` детерминированно
   собирает из него LSS JSON — код, а не модель, отвечает за формат.
4. Результат — `characters/<slug>/<slug>.lss.json` + `README.md` — коммитится
   в `main`, файл в `inbox/` удаляется.
5. Мастер импортирует `.lss.json` на [longstoryshort.app](https://longstoryshort.app),
   при желании правит и печатает `sheet.pdf`.

## Разовая настройка репозитория

### 1. Fine-grained personal access token (для формы)

GitHub → Settings → Developer settings → Fine-grained tokens → Generate new
token:
- Repository access: **Only select repositories** → `dnd-creator`.
- Permissions: **Contents: Read and write** (больше ничего не нужно).

Токен вводится прямо в форме на сайте и хранится только в localStorage
браузера — нигде больше он не сохраняется и не передаётся, кроме запросов
к `api.github.com`.

### 2. Claude Code GitHub App

Установи приложение [github.com/apps/claude](https://github.com/apps/claude)
на этот репозиторий — без него `claude-code-action` откажется работать.

### 3. Secret `CLAUDE_CODE_OAUTH_TOKEN`

Settings → Secrets and variables → Actions → New repository secret:
`CLAUDE_CODE_OAUTH_TOKEN` — OAuth-токен подписки Claude Code (не API key;
биллинг идёт по подписке, structured outputs недоступны, поэтому шаг
извлечения валидирует и чинит `draft.json` кодом с ретраями).

### 4. GitHub Pages

Settings → Pages → Source: **Deploy from a branch** → Branch: `main` / `/root`.
Форма будет доступна по адресу `https://dezodemius.github.io/dnd-creator/`.

## Как пользоваться формой

1. Открой страницу формы, вставь токен (один раз — можно нажать «Запомнить»).
2. Выбери режим: «Анкета игрока» (Claude придумает персонажа) или «Готовый
   персонаж» (только конвертация в LSS).
3. Заполни уровень, при желании — имя и указания мастеру.
4. Вставь текст анкеты или готового персонажа, нажми «Отправить в конвейер».
5. Следи за прогрессом во вкладке Actions — ссылка появится сразу после
   отправки.

## Если ран упал

Файл из `inbox/` не удаляется, пока обработка не завершится успешно —
значит, можно просто перезапустить обработку вручную: Actions →
«Сгенерировать персонажа» → Run workflow → укажи путь к файлу в
`inbox/` (например `inbox/20260714-153000-nimue.md`).

## Как добавить арт и PDF

`portrait.*` и `sheet.pdf` конвейер не создаёт — это ручной шаг. Экспортируй
`characters/<slug>/<slug>.lss.json` в longstoryshort.app, распечатай PDF в
`characters/<slug>/sheet.pdf`, добавь картинку как `characters/<slug>/portrait.png`
(или `.jpg`) и закоммить оба файла обычным пушем в `main`.
