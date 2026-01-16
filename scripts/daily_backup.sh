#!/bin/bash
BACKUP_DIR="/home/runner/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/nbadex_backup_${DATE}.dump"

mkdir -p "$BACKUP_DIR"

pg_dump -h /home/runner/postgres_socket -U runner -d nbadex -F c -f "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "Backup successful: $BACKUP_FILE"
    find "$BACKUP_DIR" -name "nbadex_backup_*.dump" -mtime +7 -delete
    echo "Cleaned up backups older than 7 days"
else
    echo "Backup failed!"
    exit 1
fi
