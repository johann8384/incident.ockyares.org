#!/bin/bash
docker-compose exec postgis pg_dump -U postgres emergency_ops > database/backups/backup_$(date +%Y%m%d_%H%M%S).sql
