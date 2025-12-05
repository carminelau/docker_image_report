#!/bin/bash
# Script di esempio per lavorare con i log del container Docker

# Colori per l'output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Nome del container - MODIFICA QUESTO CON IL TUO CONTAINER
CONTAINER_NAME="docker_image_report"

echo -e "${GREEN}=== Docker Log Viewer ===${NC}\n"

# Controlla se il container è in esecuzione
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo -e "${RED}Errore: Il container '$CONTAINER_NAME' non è in esecuzione.${NC}"
    echo "Container disponibili:"
    docker ps --format "table {{.Names}}\t{{.Status}}"
    exit 1
fi

echo -e "${GREEN}Container trovato: $CONTAINER_NAME${NC}\n"
echo "Scegli un'opzione:"
echo "1. Visualizza i log in tempo reale"
echo "2. Visualizza gli ultimi 50 log"
echo "3. Visualizza tutti i log"
echo "4. Cerca una parola nei log"
echo "5. Copia il file log.txt nel tuo computer"
echo "6. Visualizza solo gli errori"
echo "0. Esci"
echo ""

read -p "Inserisci il numero dell'opzione: " option

case $option in
    1)
        echo -e "${YELLOW}Visualizzando log in tempo reale (Ctrl+C per interrompere)...${NC}\n"
        docker exec "$CONTAINER_NAME" tail -f log.txt
        ;;
    2)
        echo -e "${YELLOW}Ultimi 50 log:${NC}\n"
        docker exec "$CONTAINER_NAME" tail -n 50 log.txt
        ;;
    3)
        echo -e "${YELLOW}Tutti i log:${NC}\n"
        docker exec "$CONTAINER_NAME" cat log.txt
        ;;
    4)
        read -p "Inserisci la parola da cercare: " search_word
        echo -e "${YELLOW}Risultati per '$search_word':${NC}\n"
        docker exec "$CONTAINER_NAME" grep "$search_word" log.txt || echo -e "${RED}Nessun risultato trovato.${NC}"
        ;;
    5)
        echo -e "${YELLOW}Copiando log.txt...${NC}"
        docker cp "$CONTAINER_NAME":/app/log.txt ./log.txt
        echo -e "${GREEN}Log copiato in ./log.txt${NC}"
        ;;
    6)
        echo -e "${YELLOW}Errori trovati:${NC}\n"
        docker exec "$CONTAINER_NAME" grep -i "error\|errore\|failed" log.txt || echo -e "${RED}Nessun errore trovato.${NC}"
        ;;
    0)
        echo "Arrivederci!"
        exit 0
        ;;
    *)
        echo -e "${RED}Opzione non valida.${NC}"
        exit 1
        ;;
esac
