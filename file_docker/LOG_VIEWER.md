# Visualizzazione dei Log in Docker

Il file `log.txt` viene generato automaticamente durante l'esecuzione dello script Python e contiene tutti i messaggi che sarebbero stati stampati a console.

## Come visualizzare i log

### 1. **Visualizzare i log in tempo reale dal container in esecuzione**

```bash
docker exec <container_name> tail -f log.txt
```

Sostituisci `<container_name>` con il nome del tuo container (es: `my-report-container`)

### 2. **Visualizzare tutti i log**

```bash
docker exec <container_name> cat log.txt
```

### 3. **Copiare il log dal container al tuo computer**

```bash
docker cp <container_name>:/app/log.txt ./log.txt
```

### 4. **Visualizzare gli ultimi N righe**

```bash
docker exec <container_name> tail -n 50 log.txt
```

Questo mostrerà le ultimi 50 righe

### 5. **Filtrare i log per parola chiave**

```bash
docker exec <container_name> grep "ERROR" log.txt
```

Questo mostrerà solo le righe contenenti "ERROR"

## Formato dei Log

Ogni riga del log ha il seguente formato:

```
[YYYY-MM-DD HH:MM:SS] Messaggio
```

Esempio:
```
[2024-12-05 14:23:45] Absolute path: /app
[2024-12-05 14:23:45] Font path: /app/fonts
[2024-12-05 14:23:46] Stato richiesta download dati: 200
```

## Note

- Il file `log.txt` viene ricreato (cancellato) ogni volta che lo script viene avviato
- Se il container non è in esecuzione, puoi comunque accedere ai log copiandoli fuori dal container
- I log contengono sia timestamp che il messaggio originale della print()
