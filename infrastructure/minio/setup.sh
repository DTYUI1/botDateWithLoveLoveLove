#!/bin/bash
# MinIO Setup Script
# Создание bucket'ов и настройка политик доступа

set -e

: "${MINIO_ENDPOINT:?MINIO_ENDPOINT is required}"
: "${MINIO_ACCESS_KEY:?MINIO_ACCESS_KEY is required}"
: "${MINIO_SECRET_KEY:?MINIO_SECRET_KEY is required}"

echo "🚀 Setting up MinIO..."

# Ждём запуска MinIO
echo "⏳ Waiting for MinIO to be ready..."
until curl -f http://${MINIO_ENDPOINT}/minio/health/live &> /dev/null; do
    sleep 2
done

echo "✅ MinIO is ready!"

# Устанавливаем MinIO Client (mc) если не установлен
if ! command -v mc &> /dev/null; then
    echo "📦 Installing MinIO Client..."
    wget https://dl.min.io/client/mc/release/linux-amd64/mc -O /usr/local/bin/mc
    chmod +x /usr/local/bin/mc
fi

# Настраиваем алиас
mc alias set myminio "http://${MINIO_ENDPOINT}" "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}"

# Создаём bucket для фотографий профилей
echo "📁 Creating bucket: profile-photos..."
mc mb myminio/profile-photos --ignore-existing

# Устанавливаем политику приватного доступа (только авторизованные)
echo "🔒 Setting private access policy for profile-photos..."
mc anonymous set none myminio/profile-photos

# Устанавливаем lifecycle policy (удаление старых неиспользуемых фото)
echo "🗑️ Setting lifecycle policy..."
mc ilm import myminio/profile-photos <<EOF
{
  "Rules": [
    {
      "ID": "Delete old photos",
      "Status": "Enabled",
      "Filter": {
        "Prefix": ""
      },
      "Expiration": {
        "Days": 365
      }
    }
  ]
}
EOF

echo "✅ MinIO setup completed!"
echo "📊 Access MinIO Console: http://localhost:9001"
echo "   Bucket: profile-photos"
echo "   Access Key: ${MINIO_ACCESS_KEY}"
echo "   Secret Key: <redacted>"
