# Telegram Shop Bot (aiogram v3) — подробная инструкция
Кодировка файла: UTF-8.

Телеграм‑бот магазина с оплатой по фото, админ‑панелью в группе и поддержкой через группу. Товары штучные: один товар можно купить только один раз. Валюта: гривны (грн).

## Что умеет
Пользователь:
1. Каталог: город → местность → вариант → классификация.
2. Корзина, оформление заказа, отправка фото оплаты.
3. Получение товара после подтверждения оплаты.
4. Поддержка после первой покупки.

Админ:
1. Админ‑панель в группе `/admin` (закрепляется кнопка «Открыть панель»).
2. Добавление товара (пошаговый мастер).
3. Управление городами и местностями (добавить/переименовать/удалить).
4. Управление вариантами и классификациями (добавить/переименовать/удалить).
5. Управление фото вариантов.
6. История покупок пользователя.
7. Кто купил товар.
8. Ассортимент (только доступные товары).
9. Скрытие товара (без удаления истории).
10. Заявки на подтверждение оплаты.
11. Статистика.
12. Логи.
13. Отчёт по оплатам (CSV).
14. Реквизиты оплаты (редактируются из админ‑панели).

## Быстрый старт (Windows)
1. Создайте виртуальное окружение и активируйте:
```powershell
cd d:\botdone
python -m venv venv
.\venv\Scripts\activate
```
2. Установите зависимости:
```powershell
pip install aiogram aiosqlite
```
3. Заполните `.env`:
```
BOT_TOKEN=ВАШ_ТОКЕН_БОТА
ADMIN_IDS=873275713
ADMIN_GROUP_ID=-1003777622502
```
4. Запуск:
```powershell
python main.py
```

## Быстрый старт (Ubuntu/WSL)
1. Установите зависимости Python:
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```
2. Перейдите в проект и создайте окружение:
```bash
cd ~/botdone
python3 -m venv venv
source venv/bin/activate
```
3. Установите зависимости:
```bash
pip install aiogram aiosqlite
```
4. Заполните `.env` и запустите:
```bash
python main.py
```

## Настройка BotFather
Рекомендуется отключить режим приватности, чтобы бот видел сообщения в группе.
В BotFather:
1. `/setprivacy`
2. выбрать бота
3. `Disable`

## Админ‑группа
1. Добавьте бота в админ‑группу.
2. Дайте права администратора.
3. В `.env` укажите `ADMIN_GROUP_ID`.

## Админ‑панель (структура)
Меню разделено на разделы, чтобы не перегружать экран.
- Каталог
- Локации
- Варианты/Классы
- Покупки/Отчеты

## Управление реквизитами
Реквизиты оплаты редактируются из админ‑панели. Новые реквизиты сохраняются в БД и показываются пользователям при оплате.

## Отчёт по оплатам
В админ‑панели есть кнопка «Отчет». Формируется файл `data/payments_report.csv` и отправляется администратору.

## Самопроверка (для автозапуска)
Скрипт проверяет `.env`, доступность логов/БД, наличие основных таблиц и базовые справочники.
```powershell
python scripts\self_check.py
```
```bash
python scripts/self_check.py
```

## Запуск на сервере через systemd (Ubuntu)
Создайте файл сервиса, например `/etc/systemd/system/botdone.service`:
```ini
[Unit]
Description=Botdone Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/USER/botdone
ExecStart=/home/USER/botdone/venv/bin/python /home/USER/botdone/main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```
Применение:
```bash
sudo systemctl daemon-reload
sudo systemctl enable botdone
sudo systemctl start botdone
sudo systemctl status botdone
```

## Логи
Файл: `logs/bot.log`

## Проверка кода
```powershell
python -m py_compile main.py app\config.py app\db\database.py app\handlers\user.py app\handlers\admin.py app\services\catalog.py
```
```bash
python -m py_compile main.py app/config.py app/db/database.py app/handlers/user.py app/handlers/admin.py app/services/catalog.py
```
