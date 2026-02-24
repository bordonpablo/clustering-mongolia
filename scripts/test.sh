#!/usr/bin/env bash
# test.sh — prueba las funcionalidades de variables derivadas agregadas al pipeline

set -e  # detener si cualquier comando falla


clustering-mongolia process-data

clustering-mongolia create-cluster
