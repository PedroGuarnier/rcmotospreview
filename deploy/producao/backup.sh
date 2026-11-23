#!/bin/sh
# Backup automático: banco todo dia, fotos uma vez por semana. Fica em ./backups no servidor.
# Um backup que só existe no mesmo servidor não protege de perda do servidor:
# copie a pasta ./backups para fora (ver LEIA-ME.md).
set -eu

MANTER_BANCO_DIAS=14
MANTER_FOTOS_DIAS=21

fazer_backup() {
  agora=$(date +%Y%m%d-%H%M)
  destino="/backups/banco-$agora.sql.gz"
  # Grava num arquivo temporário e só renomeia se o dump terminar: nunca fica backup pela metade.
  if pg_dump --no-owner > "$destino.sql.parcial" && gzip -c "$destino.sql.parcial" > "$destino.parcial"; then
    mv "$destino.parcial" "$destino"
    echo "$(date '+%d/%m/%Y %H:%M') banco salvo em $destino ($(du -h "$destino" | cut -f1))"
  else
    echo "$(date '+%d/%m/%Y %H:%M') ERRO: o backup do banco falhou" >&2
  fi
  rm -f "$destino.sql.parcial" "$destino.parcial"

  # Fotos: aos domingos, ou se ainda não houver nenhum backup de fotos
  if [ "$(date +%u)" = "7" ] || ! ls /backups/fotos-*.tar.gz >/dev/null 2>&1; then
    fotos="/backups/fotos-$agora.tar.gz"
    if tar -czf "$fotos.parcial" -C /fotos .; then
      mv "$fotos.parcial" "$fotos"
      echo "$(date '+%d/%m/%Y %H:%M') fotos salvas em $fotos ($(du -h "$fotos" | cut -f1))"
    else
      echo "$(date '+%d/%m/%Y %H:%M') ERRO: o backup das fotos falhou" >&2
    fi
    rm -f "$fotos.parcial"
  fi

  find /backups -name 'banco-*.sql.gz' -mtime +"$MANTER_BANCO_DIAS" -delete
  find /backups -name 'fotos-*.tar.gz' -mtime +"$MANTER_FOTOS_DIAS" -delete
}

# Um backup logo ao subir, depois todo dia às 3h (horário do Piauí).
fazer_backup
while true; do
  agora=$(date +%s)
  amanha=$(date -d "@$((agora + 86400))" +%Y-%m-%d 2>/dev/null || date +%Y-%m-%d)
  proximo=$(date -d "$amanha 03:00:00" +%s 2>/dev/null || echo $((agora + 86400)))
  [ "$proximo" -gt "$agora" ] || proximo=$((agora + 86400))
  sleep $((proximo - agora))
  fazer_backup
done
