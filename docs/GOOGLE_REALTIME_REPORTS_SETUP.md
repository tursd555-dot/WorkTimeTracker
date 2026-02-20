# Realtime выгрузка операторов в Google Sheets (без своего сервера)

Этот вариант работает полностью на стороне **Supabase**:

- источник: `work_log` (события `LOGIN`, `LOGOUT`, `STATUS_CHANGE`);
- запуск: **каждую минуту**;
- выгрузка: в **один общий лист** Google Sheets;
- без backfill (история не тащится, стартуем "сейчас", как вы и просили).

---

## Что уже добавлено в репозиторий

1. SQL:
   - `supabase/sql/google_rt_worklog_sync.sql`
   - создаёт таблицу чекпоинта `google_reports_sync_state`;
   - создаёт RPC `get_worklog_events_for_google_sync(...)`.

2. Supabase Edge Function:
   - `supabase/functions/google-rt-worklog-sync/index.ts`
   - читает новые события из Supabase, апендит в Google Sheet, сохраняет checkpoint.

---

## Шаг 1. Подготовить Google таблицу

Целевая таблица уже есть:

- https://docs.google.com/spreadsheets/d/1oaaGTSFTHGd9N_yKqnIdZKsMNk3HaELs_BgspT6Z42Q/edit

Что нужно сделать:

1. Создать сервисный аккаунт в Google Cloud (если ещё нет).
2. Скачать JSON-ключ сервисного аккаунта.
3. Дать сервисному аккаунту доступ к таблице (Editor):
   - **Share** → e-mail сервисного аккаунта (`...@...iam.gserviceaccount.com`).

> Без этого Google API не сможет писать в таблицу.

---

## Шаг 2. Применить SQL в Supabase

В Supabase SQL Editor выполните содержимое файла:

- `supabase/sql/google_rt_worklog_sync.sql`

После выполнения появятся:

- `public.google_reports_sync_state`
- `public.get_worklog_events_for_google_sync(...)`

---

## Шаг 3. Деплой Edge Function

Из корня проекта:

```bash
supabase functions deploy google-rt-worklog-sync
```

---

## Шаг 4. Задать secrets в Supabase

Нужные secrets:

- `GOOGLE_SPREADSHEET_ID=1oaaGTSFTHGd9N_yKqnIdZKsMNk3HaELs_BgspT6Z42Q`
- `GOOGLE_REPORTS_SHEET_NAME=RT_Events`
- `GOOGLE_SERVICE_ACCOUNT_EMAIL=<email сервисного аккаунта>`
- `GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY=<private key из JSON>`
- `REPORTS_TIMEZONE=Europe/Moscow`
- `REPORTS_BATCH_SIZE=500`
- `REPORTS_MAX_LOOPS=6`
- `SYNC_WEBHOOK_SECRET=<случайная строка>`

Важно для private key:

- если задаёте через UI, вставляйте как есть;
- если через CLI, переносы строк обычно нужно передавать как `\n`.

---

## Шаг 5. Настроить запуск каждую минуту

### Вариант A (предпочтительный): Scheduled Function в Supabase Dashboard

Создайте расписание на `* * * * *` и вызывайте:

- `POST /functions/v1/google-rt-worklog-sync`
- заголовок: `x-sync-secret: <SYNC_WEBHOOK_SECRET>`

### Вариант B: pg_cron + net.http_post

Если хотите SQL-расписание, можно через `pg_cron` и `pg_net`.
Рекомендуется сначала проверить доступность этих расширений в вашем проекте.

---

## Первая синхронизация (поведение)

На **первом запуске** функция:

- создаёт checkpoint;
- **не выгружает старую историю** (skip history);
- начинает выгружать только новые события после инициализации.

Это соответствует вашему требованию "backfill не обязателен".

---

## Какие колонки будут в листе

Лист `RT_Events` получает строки (только локальное время):

1. `EventId`
2. `Email`
3. `Name`
4. `Group`
5. `SessionID`
6. `ShiftStartLocal`
7. `ShiftEndLocal`
8. `ShiftDuration`
9. `ActionType`
10. `Status`
11. `StatusStartLocal`
12. `StatusEndLocal`
13. `StatusDuration`
14. `Comment`

`StatusEndLocal`/`StatusDuration` заполняются, когда статус завершён следующим событием.
Событие `LOGOUT` выгружается отдельной строкой (для наглядной фиксации времени выхода).

---

## Почему выбран такой вариант для "разбивки по группам"

Вы просили выбрать лучший вариант.

Использован подход **snapshot в момент выгрузки**:

- в строку сразу пишется `Group`;
- потом строка не переписывается;
- группировка в отчёте делается Pivot/Filter прямо в Google Sheets.

Это максимально простой и устойчивый путь для старта с одним листом.

---

## Быстрая проверка после запуска

1. Оператор логинится/меняет статус/разлогинивается.
2. В течение минуты в `RT_Events` появляется новая строка.
3. В `google_reports_sync_state` обновляются:
   - `last_created_at`
   - `last_event_id`
   - `updated_at`

---

## Если хотите следующим шагом

Легко расширяется до:

- отдельных листов по группам;
- сводного листа `RT_Summary`;
- алертов при задержке синка > N минут.
