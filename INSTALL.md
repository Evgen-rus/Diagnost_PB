# Инструкция по установке и настройке Telegram-бота "Диагност ПБ"

## 1. Клонирование репозитория

```bash
git clone https://github.com/Evgen-rus/Diagnost_PB.git /opt/diagnost_pb
```

или

```bash
git clone https://github.com/Evgen-rus/Diagnost_PB.git .
```


## 2. Настройка виртуального окружения

```bash
# Создание виртуального окружения
python3 -m venv venv

# Активация окружения
source venv/bin/activate

# Создание директории для логов
mkdir -p logs

# Создание директории для данных
mkdir -p data

# Установка зависимостей
pip install -r requirements.txt
```

## 3. Настройка конфигурации

```bash
# Создание файла конфигурации из примера
cp .env.example .env

# Редактирование конфигурации
nano .env
```

Содержимое файла .env:

```
# Telegram Bot
TELEGRAM_BOT_TOKEN=ваш_токен_от_BotFather

# OpenAI API
OPENAI_API_KEY=ваш_ключ_api_openai
OPENAI_MODEL=ваша_модель_openai

# Logging
LOG_LEVEL=INFO
ENABLE_DIALOG_LOGGING=true
```

## 4. Настройка автозапуска

```bash
# Создание файла службы
nano /etc/systemd/system/diagnost-pb-bot.service
```

Содержимое файла службы:

```ini
[Unit]
Description=Diagnost PB Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/diagnost_pb
Environment=PATH=/opt/diagnost_pb/venv/bin:$PATH
ExecStart=/opt/diagnost_pb/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## 5. Запуск бота

```bash
# Перезагрузка конфигурации systemd
systemctl daemon-reload

# Включение автозапуска
systemctl enable diagnost-pb-bot

# Запуск службы
systemctl start diagnost-pb-bot

# Проверка статуса
systemctl status diagnost-pb-bot
```

## 6. Полезные команды для управления ботом

```bash
# Просмотр логов в реальном времени
journalctl -u diagnost-pb-bot -f

# Просмотр последних 100 строк логов
journalctl -u diagnost-pb-bot -n 100

# Перезапуск бота
systemctl restart diagnost-pb-bot

# Остановка бота
systemctl stop diagnost-pb-bot

# Отключение автозапуска
systemctl disable diagnost-pb-bot

# Просмотр всех Python процессов
ps aux | grep python
```

## 7. Обновление бота

```bash
# Переход в директорию бота
cd /opt/diagnost_pb

# Остановка сервиса
systemctl stop diagnost-pb-bot

# Получение последних изменений
git pull

# Активация окружения
source venv/bin/activate

# Обновление зависимостей
pip install -r requirements.txt

# Запуск сервиса
systemctl start diagnost-pb-bot
```

## 8. Проверка работоспособности

После запуска бота откройте Telegram и найдите вашего бота по имени, которое вы указали при создании токена в BotFather. Отправьте команду `/start` для начала взаимодействия.

## 9. Устранение неполадок

Если бот не отвечает, проверьте:

- Статус службы: `systemctl status diagnost-pb-bot`
- Логи сервиса: `journalctl -u diagnost-pb-bot -n 100`
- Правильность токенов в файле .env
- Доступность API OpenAI (возможны ограничения по региону или API-ключу)
