#!/usr/bin/env bash
# test.sh — prueba las funcionalidades de variables derivadas agregadas al pipeline

set -e  # detener si cualquier comando falla

echo "============================================================"
echo "PASO 1: process-data (genera RTP, AS, TDR junto a las originales)"
echo "============================================================"
clustering-mongolia process-data

echo ""
echo "============================================================"
echo "PASO 2: create-cluster — variables originales (default)"
echo "  DEM, Mag_Final, Pot_final, Tho_Final, Ura_Final"
echo "============================================================"
clustering-mongolia create-cluster

echo ""
echo "============================================================"
echo "PASO 3: create-cluster — AS en lugar de Mag_Final"
echo "  DEM, AS, Pot_final, Tho_Final, Ura_Final"
echo "============================================================"
clustering-mongolia create-cluster \
  --features DEM \
  --features AS \
  --features Pot_final \
  --features Tho_Final \
  --features Ura_Final

echo ""
echo "============================================================"
echo "PASO 4: create-cluster — RTP en lugar de Mag_Final"
echo "  DEM, RTP, Pot_final, Tho_Final, Ura_Final"
echo "============================================================"
clustering-mongolia create-cluster \
  --features DEM \
  --features RTP \
  --features Pot_final \
  --features Tho_Final \
  --features Ura_Final

echo ""
echo "============================================================"
echo "PASO 5: create-cluster — todas las variables magnéticas derivadas"
echo "  DEM, Mag_Final, RTP, AS, TDR, Pot_final, Tho_Final, Ura_Final"
echo "============================================================"
clustering-mongolia create-cluster \
  --features DEM \
  --features Mag_Final \
  --features RTP \
  --features AS \
  --features TDR \
  --features Pot_final \
  --features Tho_Final \
  --features Ura_Final

echo ""
echo "============================================================"
echo "Todas las corridas finalizaron. Resultados en output/"
echo "============================================================"
