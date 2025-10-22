#!/bin/bash

# Имя окружения conda
CONDA_ENV_NAME="whisper-api"

# Флаг обновления (по умолчанию false)
UPDATE_ENV=false

# Проверка наличия аргумента --update
if [[ "$1" == "--update" ]]; then
    UPDATE_ENV=true
fi

# Проверка наличия conda
if ! command -v conda &> /dev/null; then
    echo "Conda не установлен. Пожалуйста, установите conda и попробуйте снова."
    exit 1
fi

# Флаг, указывающий, было ли создано новое окружение
NEW_ENV_CREATED=false

# Создание окружения conda, если оно не существует
if ! conda env list | grep -q "$CONDA_ENV_NAME"; then
    echo "Создание окружения conda: $CONDA_ENV_NAME"
    conda create -n "$CONDA_ENV_NAME" python=3.12 -y
    NEW_ENV_CREATED=true
else
    echo "Окружение conda '$CONDA_ENV_NAME' уже существует."
fi

# Получение пути к conda
CONDA_PATH=$(which conda)

# Проверка, что путь к conda найден
if [ -z "$CONDA_PATH" ]; then
    echo "Не удалось найти путь к conda. Убедитесь, что conda установлен и добавлен в PATH."
    exit 1
fi

# Активация окружения conda
echo "Активация окружения conda: $CONDA_ENV_NAME"
source $(dirname "$CONDA_PATH")/../etc/profile.d/conda.sh
conda activate "$CONDA_ENV_NAME"

# Установка зависимостей при первом создании окружения или при флаге --update
if [[ "$NEW_ENV_CREATED" == true || "$UPDATE_ENV" == true ]]; then
    # Установка зависимостей из requirements.txt
    if [ -f "requirements.txt" ]; then
        echo "Установка зависимостей из requirements.txt"
        pip install --no-cache-dir -r requirements.txt
    else
        echo "Файл requirements.txt не найден. Убедитесь, что он находится в той же директории, что и скрипт."
        exit 1
    fi
fi

# Запуск сервера
echo "Запуск сервера..."
python server.py --config config.json

echo "Сервер остановлен."
