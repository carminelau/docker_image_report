from io import BytesIO
from io import StringIO
import time
import PyPDF2
import numpy as np
import pandas as pd
import pytz
import requests
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, Frame, ListFlowable, ListItem, Table, TableStyle, SimpleDocTemplate, Image, PageBreak
from reportlab.pdfgen import canvas
from PyPDF2 import PdfFileReader, PdfFileWriter, PdfReader, PdfMerger, PdfWriter
from datetime import datetime, timedelta
from widget_picture_generator import widget_picture_generator
import os
import json
import openai
import re
import google.generativeai as genai
from traceback import format_exc

genai.configure(api_key="AIzaSyCKL493mVFUdgcSATpsZzlAZM8BAtalCl4")

LINGUA = "it"

ABSOLUTE_PATH = os.path.dirname(os.path.abspath(__file__))
ABSOLUTE_PATH_FONT = os.path.join(ABSOLUTE_PATH, "fonts")
ABSOLUTE_PATH_IMG = os.path.join(ABSOLUTE_PATH, "img")
ABSOLUTE_PATH_LANG = os.path.join(ABSOLUTE_PATH, "languages")
ABSOLUTE_PATH_REPORT = os.path.join(ABSOLUTE_PATH, "reports", "temp")
ABSOLUTE_PATH_REPORT_FINALI = os.path.join(ABSOLUTE_PATH, "reports", "finali")

server = "https://square.sensesquare.eu"

nomi_inquinanti = {"pm2_5": "PM2.5", "pm10": "PM10", "co": "CO",
                   "no2": "NO2", "o3": "O3", "so2": "SO2", "pm1": "PM1", "temperatura": "Temperatura", "umidita": "Umidità", "aqi": "AQI"}

colori_centraline = ["#ff9800", "#4caf50", "#26a69a", "#2196f3",
                     "#673ab7", "#9c27b0", "#f06292", "#8d6e63", "#ffeb3b"]

limiti_inquinanti = {"pm2_5": 25, "pm10": 50, "co": 10,
                     "no2": 200, "o3": 120, "so2": 350, "pm1": 10, "temperatura": 40, "umidita": 80, "aqi": 100}

ordine_inquinanti = ["aqi", "pm10", "pm2_5", "pm1",
                     "co", "no2", "o3", "so2", "temperatura", "umidita"]

pdfmetrics.registerFont(TTFont('Arial', f'{ABSOLUTE_PATH_FONT}/Arial.ttf'))
pdfmetrics.registerFont(
    TTFont('Times New Roman', f'{ABSOLUTE_PATH_FONT}/times-new-roman.ttf'))
pdfmetrics.registerFont(
    TTFont('Calibri', f'{ABSOLUTE_PATH_FONT}/calibrii.ttf'))
pdfmetrics.registerFont(
    TTFont('Poppins', f'{ABSOLUTE_PATH_FONT}/Poppins-Black.ttf'))

tz = "Europe/Rome"

# Creazione degli stili
styles = getSampleStyleSheet()
normal_style = styles['Normal']
heading_style = styles['Heading2']
bullet_style = styles['Bullet']
# aggiungi agli style lo style Caption
styles.add(ParagraphStyle(name='Caption', parent=styles['Normal']))
styles.add(ParagraphStyle(name='Table Column', parent=styles['Normal']))
styles.add(ParagraphStyle(name='Table Row', parent=styles['Normal']))
styles.add(ParagraphStyle(name='normal_spaced', parent=styles['Normal']))

# Funzione per applicare Paragraph a tutto il testo della tabella


def create_paragraph(text, style_name='Normal'):
    # Imposta il colore del testo per lo stile Heading3
    if style_name == 'Heading3':
        styles[style_name].textColor = colors.whitesmoke
        styles[style_name].fontName = 'Helvetica-Bold'
        styles[style_name].fontSize = 8
        styles[style_name].leading = 8
    elif style_name == "Caption":
        styles[style_name].textColor = colors.black
        styles[style_name].fontName = 'Helvetica'
        styles[style_name].fontSize = 6
        styles[style_name].leading = 6
        # centra il testo
        styles[style_name].alignment = 1
        styles[style_name].spaceBefore = 4
        styles[style_name].spaceAfter = 6
    elif style_name == "Table Column":
        styles[style_name].textColor = colors.whitesmoke
        styles[style_name].fontName = 'Helvetica-Bold'
        styles[style_name].fontSize = 10
        styles[style_name].leading = 10
    elif style_name == "Table Row":
        styles[style_name].textColor = colors.black
        styles[style_name].fontName = 'Helvetica'
        styles[style_name].fontSize = 8
        styles[style_name].leading = 8
    elif style_name == "normal_spaced":
        styles[style_name].textColor = colors.black
        styles[style_name].fontName = 'Helvetica'
        styles[style_name].spaceBefore = 4
    else:
        styles[style_name].textColor = colors.black
        styles[style_name].fontName = 'Helvetica'
        styles[style_name].fontSize = 6
        # riduci interlinea
        styles[style_name].leading = 6
    return Paragraph(text, styles[style_name])


lim = {
    "no2": {
        "media": "oraria",
        "limite": 200
    },
    "co": {
        "media": "oraria",
        "limite": 10
    },
    "pm10": {
        "media": "oraria",
        "limite": 50
    },
    "pm2_5": {
        "media": "oraria",
        "limite": 25
    },
    "o3": {
        "media": "oraria",
        "limite": 180
    }
}


def generate_text_sensesquare(model, prompt) -> str:
    url = f'https://ai.sensesquare.eu/ollamaapi/api/generate'
    payload = {'model': model, 'prompt': prompt, "stream": False}
    headers = {'Content-Type': 'application/json'}

    response = requests.post(url, data=json.dumps(payload), headers=headers)

    print("generata da sensesquare")

    return response.json()["response"]


def open_file(file_name):
    return json.loads(open(f"{ABSOLUTE_PATH_LANG}/{file_name}", "r").read())


avail_lang = {
    "it": open_file("italian.json"),
    "en": open_file("english.json")
}


def retrieve_project(apikey: str) -> list:
    url = f"{server}:5002/elenco_progetti"
    req = requests.post(url, {"apikey": apikey})

    return req.json()["result"]


def ultimo_giorno_mese_precedente(mese, anno):
    primo_giorno_mese = datetime(anno, mese, 1)
    ultimo_giorno_precedente = primo_giorno_mese - timedelta(days=1)
    return ultimo_giorno_precedente.day


def create_air_quality_table():

    # Dati della tabella con Paragraph applicato

    # Definisci larghezze delle colonne proporzionate per A4 verticale
    col_widths = [60, 70, 60, 70, 150]  # Regola le larghezze
    # Altezza fissa per le righe dei dati
    row_heights = [30] + [20] * (len(data) - 1)

    # Crea la tabella e specifica larghezze delle colonne e altezze delle righe
    table = Table(data, colWidths=col_widths, rowHeights=row_heights)

    # Applica lo stile alla tabella
    style = TableStyle([
        # Sfondo per la riga di intestazione
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#009688")),

        # Colore del testo dell'intestazione
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  # Allinea il testo al centro
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Font dell'intestazione
        ('FONTSIZE', (0, 0), (-1, 0), 8),  # Dimensione font dell'intestazione
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),  # Padding per l'intestazione
        # Dimensione font delle righe dei dati
        ('FONTSIZE', (0, 1), (-1, -1), 6),
        # Sfondo per le celle dei dati
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),  # Aggiungi griglia nera
        # Allinea verticalmente il testo
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])

    table.setStyle(style)

    return table


def create_styled_paragraph(text):
    if re.match(r'\*\*(.+)\*\*', text):  # Se il testo è racchiuso tra **, usa lo stile Heading1
        return Paragraph(re.sub(r'\*\*(.+)\*\*', r'\1', text), styles["Heading1"])
    else:
        return Paragraph(text, normal_style)

# Funzione per creare paragrafi formattati


def format_paragraph(text):
    # Riconosce e converte i titoli in intestazioni
    if re.match(r'\*\*(.+)\*\*', text):
        # Rimuove i ** e applica lo stile di intestazione
        return Paragraph(re.sub(r'\*\*(.+)\*\*', r'\1', text), heading_style)
    else:
        # Paragrafo normale
        return Paragraph(text, normal_style)

# Funzione per riconoscere le liste puntate e formattarle


def format_bullet_list(text_lines):
    list_items = []
    for line in text_lines:
        list_items.append(ListItem(Paragraph(line.strip('* '), bullet_style)))
    return ListFlowable(list_items, bulletType='bullet')


def translation(language, key, to_format="None"):
    if language in avail_lang:
        language = language
    else:
        language = "en"
    if key in avail_lang[language]:
        format_params = []
        if to_format != "None":
            format_params = avail_lang[language]["found_params"][to_format]
        if len(format_params) > 0:
            return avail_lang[language][key].format(*format_params)
        else:
            return avail_lang[language][key]
    else:
        return key


def translation_data(language: str, key: datetime, ora: bool = False):
    if language in avail_lang:
        language = language
    else:
        language = "en"

    if language == "it":
        if ora:
            return key.strftime("%d-%m-%YT%H:%M")
        else:
            return key.strftime("%d-%m-%Y")
    else:
        if ora:
            return key.strftime("%Y-%m-%dT%H:%M")
        else:
            return key.strftime("%Y-%m-%d")


def path_templates() -> list:
    lista = []
    lista.append(os.path.join(
        ABSOLUTE_PATH, "templates", "Template_Iniziale.png"))
    lista.append(os.path.join(
        ABSOLUTE_PATH, "templates", "Template_Pagina.png"))

    return lista


lista_template = path_templates()


def download_dati(place: dict, datainizio: datetime, datafine: datetime, req_type, zoom: int, fonte: str):
    apikey = "WDBNX4IUF66C"

    # Tipo di dati richiesti: medie giornaliere, medie orarie, medie al minuto, dati grezzi. I dati grezzi e le medie al minuto sono disponibili solo per zoom compreso tra 3 e 5 (inclusi).
    # tipi di dato: "daily", "hourly", "instant", "raw"

    # zoom = 1 per le nazioni
    # zoom = 2 per le regioni
    # zoom = 3 per le province
    # zoom = 4 per i comuni
    # zoom = 5 per le centraline

    try:
        # localizzare datainizio e datafine
        datainizio = pytz.timezone(tz).localize(datainizio)
        datafine = pytz.timezone(tz).localize(datafine)

    except:
        datainizio = datainizio
        datafine = datafine

    # Data a partire dalla quale si richiedono i dati. Il formato è del tipo anno-mese-giorno separati da "-".
    start_date = datainizio.strftime("%Y-%m-%dT%H:%M:%S%z").replace("+", "%2B")

    # Data finale per i dati richiesti. Il formato è del tipo anno-mese-giorno separati da "-".
    end_date = datafine.strftime("%Y-%m-%dT%H:%M:%S%z").replace("+", "%2B")

    # formato dei dati: json, csv o xlsx
    formato = 'csv'

    # Stringa contenente un array delle fonti delle quali si richiedono le medie. Se l’array non presenta alcun elemento, la media restituita conterrà i contributi di tutte le fonti a disposizione per il luogo scelto
    # fonte = '[]' significa che si vogliono tutte le fonti disponibili
    # fonte = '["ssq"]' significa che si vogliono solo i dati di sensesquare
    # fonte = '["arpa_eea"]' significa che si vogliono solo i dati dell'arpa e eea
    # fonte  = '["copernicus"]' significa che si vogliono solo i dati di copernicus
    # fonte = '["arpa_eea", "copernicus"]' significa che si vogliono solo i dati dell'arpa e eea e di copernicus

    # ESEMPIO 1: In questo esempio proviamo a scaricare i dati dello square Salerno-Salerno 3:5
    # del giorno 15/03/2023 dalle 0 alle 23 con zoom 4 e formato json di tutte le fonti disponibili

    # ESEMPIO METODO GET

    # Creazione dell'url per il metodo GET concatenando i vari parametri che ci servono
    url = f"{server}:5001/download?apikey=" + apikey + "&req_type="+req_type+"&zoom=" + str(zoom) + "&format=" + formato + "&fonte=" + \
        fonte + "&start=" + start_date + "&end=" + end_date

    zoom = int(zoom)

    if zoom == 5:
        url += "&req_centr=" + place["centralina"]
    else:
        if zoom >= 0:
            url += "&nazione=" + place["nazione"]
        if zoom >= 1:
            url += "&regione=" + place["regione"]
        if zoom >= 2:
            url += "&provincia=" + place["provincia"]
        if zoom >= 3:
            url += "&comune=" + place["comune"]
        if zoom >= 4:
            url += "&squareID=" + place["squareID"]

    print("-------------------")
    print(url)
    print("-------------------")
    # Richiesta GET
    req = requests.get(url)

    result = ""
    if "\"response_code\":300" in req.text:
        print("download Posposto")
        result = req.json()["result"]
        pending = True
        while pending:
            url = f"{server}:5001/ping_download"
            req = requests.post(url, {"apikey": apikey, "obj_id": result})
            print(req.text)

            if req.json()["response_code"] == 200:
                pending = False
                result = req.json()["result"]

            time.sleep(10)

        url = f"{server}:5001/download_posposto"
        req = requests.post(
            url, {"apikey": apikey, "obj_id": result}, stream=True)

        return req.content
    else:
        return req.content


def path_photos(type_photo: str) -> list:
    lista = []

    if type_photo == "mappa":
        for f in os.listdir(ABSOLUTE_PATH_IMG):
            if f.startswith("mappa"):
                lista.append(os.path.join(ABSOLUTE_PATH_IMG, f))
    else:
        for f in os.listdir(ABSOLUTE_PATH_IMG):
            if not f.startswith("mappa"):
                lista.append(os.path.join(ABSOLUTE_PATH_IMG, f))

    return lista


def retrieve_project(apikey: str) -> list:
    url = f"{server}:5002/elenco_progetti"
    req = requests.post(url, {"apikey": apikey})

    return req.json()["result"]


def analisi_sforamenti(luogo: dict, start: datetime, end: datetime, type_data: str, zoom: int, font: str, pro: False):
    # Crea il DataFrame dal CSV

    df = pd.read_csv(StringIO(download_dati(luogo, start, end,
                     type_data, zoom, font).decode('utf-8')))

    # Verifica sforamenti
    sforamenti = pd.DataFrame()

    df.columns = df.columns.str.replace(r"\[.*\]", "", regex=True).str.strip()

    for inquinante, limite in lim.items():
        if inquinante in df.keys():
            sforamenti[inquinante] = df[inquinante] > limite["limite"]

    # Mostra solo le righe in cui c'è almeno uno sforamento
    sforamenti_righe = sforamenti.any(axis=1)

    print(sforamenti)
    print(sforamenti_righe)

    # Output con righe che contengono sforamenti
    df_sforamenti = df[sforamenti_righe]

    print("Righe con sforamenti:")
    print(df_sforamenti)

    if len(df_sforamenti) > 0:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            "Mi scrivi un testo dove descrivi i vari sforamenti che ci sono stati: (senza usare elenchi puntati) Indicando anche il nome del sensore e escludendo l'analisi sull'AQI ed il valore della timezone \n" + df_sforamenti.to_string())
    else:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            "Mi descrivi l'andamento dell'inquinamento dei seguenti dati: (senza usare elenchi puntati) Indicando anche il nome del sensore e escludendo l'analisi sull'AQI ed il valore della timezone\n" + df.to_string())

    lines = response.text.strip().split('\n')

    for line in lines:
        if line.startswith('*'):  # Se è una lista puntata
            return format_bullet_list([line])
        else:
            return format_paragraph(line)


def retrieve_project_by_id(apikey: str, project_id: str) -> dict:
    url = f"{server}:5002/elenco_progetti"
    req = requests.post(url, {"apikey": apikey})

    for project in req.json()["result"]:
        if project["id_progetto"] == project_id:
            return project

    return None


def get_start_end_date(freq: str, pro: dict = {}, dati=False):
    data_focus = datetime.now()

    if "datastart" in pro.keys():
        data_focus = pro["datastart"]

    datainizio = pytz.timezone(tz).localize(
        data_focus.replace(hour=0, minute=0, second=0, microsecond=0))
    datafine = pytz.timezone(tz).localize(data_focus.replace(
        hour=23, minute=59, second=59, microsecond=0))

    if freq == "giornalieri":
        datainizio = (data_focus - timedelta(days=1)
                      ).replace(hour=0, minute=0, second=0, microsecond=0)
        datafine = (data_focus - timedelta(days=1)
                    ).replace(hour=23, minute=59, second=59, microsecond=0)
    elif freq == "settimanali":
        datainizio = (data_focus - timedelta(days=7)
                      ).replace(hour=0, minute=0, second=0, microsecond=0)
        datafine = (data_focus - timedelta(days=1)
                    ).replace(hour=23, minute=59, second=59, microsecond=0)
    elif freq == "mensili":
        # mettere come datainizio primo giorno del mese precedente a datafocus e come fine ultimo giorno del mese precedente a datafocus

        datainizio = data_focus.replace(
            day=1, month=data_focus.month-1).replace(hour=0, minute=0, second=0, microsecond=0)
        datafine = data_focus.replace(day=ultimo_giorno_mese_precedente(
            data_focus.month-1, data_focus.year), month=data_focus.month-1).replace(hour=23, minute=59, second=59, microsecond=0)

    elif freq == "custom":

        print(pro)

        inizio = pro["intervallo"][0]
        fine = pro["intervallo"][1]

        if set(inizio.keys()) == set(["ora", "minuti"]):
            datainizio = (data_focus - timedelta(days=1)
                          ).replace(hour=int(inizio["ora"]), minute=int(inizio["minuti"]), second=0, microsecond=0)
            datafine = (data_focus - timedelta(days=1)
                        ).replace(hour=int(fine["ora"]), minute=int(fine["minuti"]), second=59, microsecond=0)
            if dati:
                dati = download_dati(
                    pro["luoghi"][0], datainizio, datafine, "hourly", str(int(pro["zoom"])), "[]")
                # Converte lo stream di byte in un oggetto leggibile da Pandas
                csv_data = BytesIO(dati)

                if len(csv_data.getvalue()) > 1:

                    # importare i dati in un dataframe tenendo conto che sono un csv sotto forma di stringa
                    df = pd.read_csv(csv_data, sep=",")

                    if len(df) > 0:

                        # prendere il timestamp del primo e dell'ultimo valore
                        datainizio = datetime.strptime(
                            df["timestamp"][0], '%Y-%m-%dT%H:%M:%S%z')
                        datafine = datetime.strptime(
                            df["timestamp"][len(df["timestamp"])-1], '%Y-%m-%dT%H:%M:%S%z')

    elif freq == "annuali":
        # mettere come datainizio primo gennaio e come fine 31 dicembre andando a cambiare solo l'anno in base a quello corrente -1 con la replace
        datainizio = (data_focus.replace(year=data_focus.year-1,
                      month=1, day=1, hour=0, minute=0, second=0, microsecond=0))
        datafine = (data_focus.replace(year=data_focus.year-1, month=12, day=31, hour=23,
                    minute=59, second=59, microsecond=0))

    return datainizio, datafine


def get_undertitle(freq: str, proj: dict) -> str:
    if freq == "custom":
        datai, dataf = get_start_end_date(freq, proj, True)
        datai = translation_data(LINGUA, datai, True)
        dataf = translation_data(LINGUA, dataf, True)
        return "Dal " + datai + " al " + dataf
    else:
        datai, dataf = get_start_end_date(freq, proj)
        datai = translation_data(LINGUA, datai)
        dataf = translation_data(LINGUA, dataf)

        if freq == "giornalieri":
            return datai
        else:
            return "Dal " + datai + " al " + dataf


def FrameHeaderAndBody(pdf, stile, fontn, campi, freq):
    undertitle = get_undertitle(freq, campi)
    flow_obj = []
    # Frame dedicati al titolo e sotto titolo(data)
    flow_obj.append(Paragraph("Report "+campi['alias_progetto'], ParagraphStyle(
        name='titolo', fontSize=fontn, leading=fontn * 1.2, fontName=stile)))
    frameTitolo = Frame(30, 240, 570, 300, showBoundary=0)
    frameTitolo.addFromList(flow_obj, pdf)

    flow_obj.append(Paragraph(undertitle, ParagraphStyle(
        name='data', fontSize=fontn-15, leading=25 * 1.2, fontName=stile)))
    frameData = Frame(30, frameTitolo._y -
                      125, 575, 120, showBoundary=0)
    frameData.addFromList(flow_obj, pdf)
    # Frame che trovi in basso a sinistra e destra
    flow_obj.append(Paragraph(translation(LINGUA, "report_automatically_generated"),
                    ParagraphStyle(name='midleft', fontSize=12, alignment=0, textColor="white", fontName=stile)))
    frameSinistro_basso = Frame(20, 120, 315, 50, showBoundary=0)
    frameSinistro_basso.addFromList(flow_obj, pdf)

    flow_obj.append(Paragraph("Sense Square S.r.l", ParagraphStyle(
        name='midright', fontSize=11, alignment=2, textColor="white", fontName=stile)))
    framedestro_tit = Frame(430, 130, 100, 30, showBoundary=0)
    framedestro_tit.addFromList(flow_obj, pdf)

    flow_obj.append(Paragraph(translation(LINGUA, "info_ssq"),
                    ParagraphStyle(name='midrighttext', fontSize=9, alignment=2, textColor="white", fontName=stile)))
    frameDestro_basso = Frame(340, 30, 230, 120, showBoundary=0)
    frameDestro_basso.addFromList(flow_obj, pdf)

# Funzione per aggiungere un PDF come sfondo ad un altro PDF


def merge_pdfs_background(background_pdf_path, content_pdf_path, output_pdf_path):
    # Apri il PDF di sfondo e il PDF con i contenuti
    with open(background_pdf_path, "rb") as bg_pdf_file, open(content_pdf_path, "rb") as content_pdf_file:
        content_pdf = PyPDF2.PdfReader(content_pdf_file)

        # Crea uno scrittore di PDF per il risultato finale
        pdf_writer = PyPDF2.PdfWriter()

        # Unisci ogni pagina di contenuto con il rispettivo sfondo
        for page_num in range(len(content_pdf.pages)):
            bg_pdf = PyPDF2.PdfReader(bg_pdf_file)

            bg_page = bg_pdf.pages[0]
            content_page = content_pdf.pages[page_num]

            # Sovrapponi le pagine
            bg_page.merge_page(content_page)

            # Aggiungi la pagina combinata al nuovo PDF
            pdf_writer.add_page(bg_page)

        # Salva il nuovo PDF
        with open(output_pdf_path, "wb") as output_pdf_file:
            pdf_writer.write(output_pdf_file)


def FrameFooter(pdf, stile):
    flow_obj = []
    # Frame che riguardano il Footer
    flow_obj.append(Paragraph("Corso Garibaldi, 33, Salerno (SA), 84123", ParagraphStyle(
        name='footer1', fontSize=9, textColor="white", fontName=stile)))
    frame_footer = Frame(20, 5, 190, 30, showBoundary=0)
    frame_footer.addFromList(flow_obj, pdf)

    flow_obj.append(Paragraph("P.IVA/C.F.: IT05466060653  info@sensesquare.eu",
                    ParagraphStyle(name='footer2', fontSize=9, textColor="white", fontName=stile)))
    frame_footer_cen = Frame(220, 5, 240, 30, showBoundary=0)
    frame_footer_cen.addFromList(flow_obj, pdf)

    flow_obj.append(Paragraph("www.sensesquare.eu", ParagraphStyle(
        name='footer3', fontSize=9, textColor="white", fontName=stile)))
    frame_footer_des = Frame(470, 5, 140, 30, showBoundary=0)
    frame_footer_des.addFromList(flow_obj, pdf)


def info_centralina(req_centr: str) -> dict:
    """
    This function retrieves information about a specific sensor station (centralina) from the SENSEable Square platform.
    It takes a string parameter 'req_centr' which is the ID of the sensor station to retrieve information for.
    It returns a dictionary containing information about the sensor station, including its latitude and longitude, geocoded address, and other metadata.
    """
    apikey = "WDBNX4IUF66C"
    print({"apikey": apikey, "ID": req_centr})
    url = f"{server}:5002/informazioni_centralina"
    req = requests.post(url, {"apikey": apikey, "ID": req_centr})
    info_ssq = dict(req.json()["result"])

    if info_ssq["type"] < 2:

        try:
            url = f"https://nominatim.openstreetmap.org/reverse?lat={info_ssq['lat']}&lon={info_ssq['lon']}&format=json&zoom=18"
            req = requests.get(url)
            info_osm = req.json()
        except:
            info_osm = {
                "error": "Errore nell'ottenere le informazioni da OpenStreetMap"}

        url = f"{server}:5001/geodecode"
        req = requests.post(
            url, {"apikey": apikey, "lat": info_ssq["lat"], "lon": info_ssq["lon"], "zoom": 4})

        info_ssq["geodecode"] = req.json()
        if "error" not in info_osm:
            if req_centr.startswith("Capannone"):
                info_ssq["indirizzo"] = "Via Ospedaletto, 331"
            else:
                try:
                    info_ssq["indirizzo"] = f"{info_osm['address']['road']}, {info_osm['address']['house_number']}"
                except:
                    info_ssq["indirizzo"] = f"{info_osm['address']['road']}"

    return info_ssq


def get_picture_geomap_centralina(nome_centralina: str):

    info_centr = info_centralina(nome_centralina)

    conf = {"source": {"type": "device", "value": {"key": info_centr["ID"], "value": info_centr["ID"], "name": info_centr["ID"]}}, "points": [{"position": {"lat": info_centr["lat"], "lng": info_centr["lon"]},
                                                                                                                                               "color": "red"}], "parameter": "aqi", "map": "standard",
            "dataSource": "prediction", "period": "giorno", "viewMode": "panoramic", "fillOpacity": 60, "_defaultStateKey": ["source", "value", "name"], "_timer_refresh": -1}

    wpg = widget_picture_generator("WDBNX4IUF66C")
    wpg.get_widget_picture_file(
        f"{ABSOLUTE_PATH_IMG}/mappa_{nome_centralina}.png", "widget_geomap_v2", conf, timeout=13)
    # Destroy the driver
    wpg.destroy()

# da modificare per farlo funzionare per i luoghi


def get_picture_geomap_place(luoghi: list, zoom: int):
    for luogo in luoghi:

        lista_nomi = list(luogo.values())

        lista_zoom_geomap = [5, 8, 10, 12, 13]

        url = "https://square.sensesquare.eu:5001/info_polygon"

        req = requests.post(
            url, {"apikey": "WDBNX4IUF66C", "zoom": zoom, "path": json.dumps(luogo)})
        
        print({"apikey": "WDBNX4IUF66C", "zoom": zoom, "path": json.dumps(luogo)})
        print(req.text)

        info_poly = req.json()["result"]

        conf = {
            "data_type": "pm10",
            "path": {
                "name": lista_nomi[zoom],
                "path": luogo,
                "zoom": lista_zoom_geomap[zoom],
                "center": info_poly["center"],
                "geolevel": zoom,
                "bounds": info_poly["bounds"]
            },
            "map_type": "Esri.WorldImagery",
            "prediction": True,
            "source_type": "all",
            "_defaultStateKey": [
                "path",
                "name"
            ],
            "_timer_refresh": -1
        }

        wpg = widget_picture_generator("WDBNX4IUF66C")
        wpg.get_widget_picture_file(
            f"{ABSOLUTE_PATH_IMG}/mappa_{lista_nomi[zoom]}.png", "widget_geomap_v2", conf, timeout=13)
        # Destroy the driver
        wpg.destroy()

# creare una funzione che dato un vettore di json, controlla i campi della chiave color e restituisce un colore che non è già stato usato


def get_color(arr: list) -> str:
    colori = ["#ff9800", "#4caf50", "#26a69a", "#2196f3",
              "#673ab7", "#9c27b0", "#f06292", "#8d6e63", "#ffeb3b", "#ff5722", "#795548", "#607d8b"]
    if len(arr) == 0:
        return colori[0]

    lista_colori = []
    for el in arr:
        lista_colori.append(el["color"])
    for col in colori:
        if col not in lista_colori:
            return col
    return colori[0]


def get_name_color(color: str) -> str:
    if color == "#ff9800":
        return "Arancione"
    if color == "#4caf50":
        return "Verde"
    if color == "#26a69a":
        return "Verde Acqua"
    if color == "#2196f3":
        return "Blu"
    if color == "#673ab7":
        return "Viola"
    if color == "#9c27b0":
        return "Viola Scuro"
    if color == "#f06292":
        return "Rosa"
    if color == "#8d6e63":
        return "Marrone"
    if color == "#ffeb3b":
        return "Giallo"
    if color == "#ff5722":
        return "Rosso"
    if color == "#795548":
        return "Marrone Scuro"
    if color == "#607d8b":
        return "Grigio"

    return ""


def get_picture_analyze_path(centraline=None, freq="", pro: dict = {}):

    if freq == "custom":
        datainizio, datafine = get_start_end_date(freq, pro, True)
    else:
        datainizio, datafine = get_start_end_date(freq, pro)

    conf = {
        "showMapFullscreen": True,
        "date": datainizio.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "mapStyle": "standard",
        "selectedPoints": {},
        "sources": []
    }

    legenda = {}

    for centralina in centraline:
        agg = {
            "color": get_color(conf["sources"]),
            "id": centralina[0:7],
            "name": centralina,
            "parameter": "none",
            "type": "device",
            "value": {
                    "name": centralina,
                    "value": centralina
            },
            "width": "6"
        }
        conf["sources"].append(agg)
        legenda.update({centralina: agg["color"]})

    wpg = widget_picture_generator("WDBNX4IUF66C")
    wpg.get_widget_picture_file(
        f'{ABSOLUTE_PATH_IMG}/mappa_{pro["alias_progetto"]}_path.png', "tool_analizza_percorsi", conf, timeout=13)
    # Destroy the driver
    wpg.destroy()

    return legenda


def get_picture_analyze_data(centraline=None, freq="", pro: dict = {}):

    if freq == "custom":
        datainizio, datafine = get_start_end_date(freq, pro, True)
    else:
        datainizio, datafine = get_start_end_date(freq, pro)

    print("-------------------")
    print(datainizio, datafine)
    print("-------------------")
    typef = ""
    if freq == "giornalieri":
        typef = "hourly"
    if freq == "settimanali":
        typef = "daily"
    if freq == "mensili":
        typef = "daily"
    if freq == "custom":
        typef = "instant"
    if freq == "annuali":
        typef = "daily"

    for inquinante in pro["inquinanti"]:

        conf = {
            "dataType": 4,
            "sources": [
                {
                    "type": "guide",
                    "source": None,
                    "parameter": inquinante,
                    "chartType": "line",
                    "yAxis": "y",
                    "selectedColor": "#e53935",
                    "smoothLine": True,
                    "showDots": True,
                    "guideValue": limiti_inquinanti[inquinante],
                    "name": f"Limite {nomi_inquinanti[inquinante]}",
                    "id": "_s9rp7lpfn"
                }
            ],
            "selectedGranularity": typef,
            "showGrid": False,
            "showLegend": True,
            "selectedRatio": 1.3333333333333333,
            "showChartFullscreen": True
        }

        if freq == "custom":
            conf["from"] = datainizio.strftime("%Y-%m-%dT%H:%M:%S%z")
            conf["to"] = datafine.replace(
                minute=59).strftime("%Y-%m-%dT%H:%M:%S%z")
        else:
            conf["from"] = datainizio.replace(
                hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S%z")
            conf["to"] = datafine.replace(
                hour=23, minute=59, second=59, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S%z")

        if pro["zoom"] == 5:
            for centralina in centraline:
                conf["sources"].append({
                    "type": "device",
                    "source": centralina,
                    "parameter": inquinante,
                    "chartType": "line",
                    "yAxis": "y",
                    "selectedColor": colori_centraline[centraline.index(centralina)],
                    "smoothLine": True,
                    "showDots": True,
                    "name": f"{centralina}",
                    "id": f"{centralina}"
                })
        else:
            for luogo in pro["luoghi"]:

                name = ""
                if pro["zoom"] == 4:
                    name = f"{luogo['squareID']}"
                if pro["zoom"] == 3:
                    name = f"{luogo['comune']}"
                if pro["zoom"] == 2:
                    name = f"{luogo['provincia']}"
                if pro["zoom"] == 1:
                    name = f"{luogo['regione']}"
                if pro["zoom"] == 0:
                    name = f"{luogo['nazione']}"

                conf["sources"].append({
                    "type": "place",
                    "source": {
                        "path": luogo,
                        "geolevel": pro["zoom"],
                    },
                    "parameter": inquinante,
                    "chartType": "line",
                    "yAxis": "y",
                    "selectedColor": colori_centraline[pro["luoghi"].index(luogo)],
                    "smoothLine": True,
                    "showDots": True,
                    "name": name,
                    "id": name,
                    "dataSource": "all"
                })

        wpg = widget_picture_generator("WDBNX4IUF66C")
        wpg.get_widget_picture_file(
            f"{ABSOLUTE_PATH_IMG}/{inquinante}_chart.png", "tool_analizza_dati", conf, timeout=15)
        # Destroy the driver
        wpg.destroy()


def conversione_frequenza(arr: list) -> list:

    output = []
    for i in range(len(arr)):
        if arr[i] == 1:
            if i == 0:
                output.append("giornalieri")
            elif i == 1:
                output.append("settimanali")
            elif i == 2:
                output.append("mensili")
            elif i == 3:
                output.append("custom")

    return output


def genera_immagini_square(pro: dict, freq: str) -> dict:
    if pro["zoom"] == 5:
        centraline = genera_lista_centraline(pro)
        get_picture_analyze_data(freq=freq, pro=pro, centraline=centraline)
        # controllare se tutti gli elementi di centraline iniziano con MM
        all_mm = True
        for centralina in centraline:
            if not centralina.startswith("MM"):
                all_mm = False
                break
        if all_mm:
            return get_picture_analyze_path(centraline=centraline, freq=freq, pro=pro)
        else:
            for centralina in centraline:
                if centralina.startswith("MM") and all_mm == False:
                    get_picture_analyze_path(
                        centraline=[centralina], freq=freq, pro=pro)
                else:
                    get_picture_geomap_centralina(centralina)
    else:
        get_picture_geomap_place(pro["luoghi"], pro["zoom"])
        get_picture_analyze_data(freq=freq, pro=pro)

    return {}


def genera_lista_centraline(progetto: dict) -> list:
    lista = []
    for item in progetto["luoghi"]:
        if "centralina" in item.keys():
            lista.append(item["centralina"])

    return lista


def genera_Pagina_chart(proj={}, freq=""):
    # Crea il PDF
    document = SimpleDocTemplate(
        f"{ABSOLUTE_PATH_REPORT}/Pagina_{proj['alias_progetto']}_Chart.pdf", pagesize=A4
    )
    elements = []

    # crea una lista che segue l'ordine degli inquinanti ma solo con quelli di cui ci sta l'immagine
    ordine = []
    for p in ordine_inquinanti:
        if p in proj["inquinanti"]:
            ordine.append(p)

    for poll in range(0, len(ordine), 2):

        # Prima immagine
        elements.append(Paragraph(
            f"{translation(LINGUA, 'graph_view')} {nomi_inquinanti[ordine[poll]]}", heading_style))
        elements.append(
            Image(f"{ABSOLUTE_PATH_IMG}/{ordine[poll]}_chart.png", width=430, height=250))

        # Seconda immagine (se esiste)
        if poll + 1 < len(ordine):
            elements.append(Paragraph("\n", heading_style))
            elements.append(Paragraph(
                f"{translation(LINGUA, 'graph_view')} {nomi_inquinanti[ordine[poll + 1]]}", heading_style))
            elements.append(Image(
                f"{ABSOLUTE_PATH_IMG}/{ordine[poll + 1]}_chart.png", width=430, height=250))

        # Aggiunge un'interruzione di pagina dopo ogni coppia di immagini
        elements.append(PageBreak(None))

    document.build(elements)

    # Percorsi ai file
    background_pdf_path = f"{ABSOLUTE_PATH}/templates/Pagine_Example.pdf"
    content_pdf_path = f"{ABSOLUTE_PATH_REPORT}/Pagina_{proj['alias_progetto']}_Chart.pdf"
    output_pdf_path = f"{ABSOLUTE_PATH_REPORT}/Pagina_{proj['alias_progetto']}_Chart.pdf"

    # Unisci il PDF di sfondo con il PDF generato
    merge_pdfs_background(background_pdf_path,
                          content_pdf_path, output_pdf_path)


def clean_img():
    for f in os.listdir(ABSOLUTE_PATH_IMG):
        os.remove(os.path.join(ABSOLUTE_PATH_IMG, f))


def genera_Pagina_mappe(proj={}, freq=""):
    # Crea il PDF
    document = SimpleDocTemplate(
        f"{ABSOLUTE_PATH_REPORT}/Pagina_{proj['alias_progetto']}_Mappe.pdf", pagesize=A4)
    elements = []
    leg = genera_immagini_square(proj, freq)

    # Genera il testo con l'elenco dei dispositivi
    righe_dispositivi = []

    if len(proj["luoghi"]) > 1:
        if proj["zoom"] == 5:
            righe_dispositivi.append(translation(LINGUA, "devices_analysis"))
        else:
            righe_dispositivi.append(translation(LINGUA, "places_analysis"))
    else:
        if proj["zoom"] == 5:
            righe_dispositivi.append(translation(LINGUA, "device_analysis"))
        else:
            righe_dispositivi.append(translation(LINGUA, "place_analysis"))

    for luogo in proj["luoghi"]:
        if proj["zoom"] == 5:
            info = info_centralina(luogo["centralina"])

            if info["type"] < 2:

                if "indirizzo" not in info.keys() and "address" not in info.keys():
                    righe_dispositivi.append(
                        f"- {info['ID']} - {info['geodecode']['comune']}")

                else:
                    if "indirizzo" in info:
                        righe_dispositivi.append(
                            f"- {info['ID']} {info['indirizzo']} - {info['geodecode']['comune']}")
                    else:
                        righe_dispositivi.append(
                            f"- {info['ID']} {info['address']} - {info['geodecode']['comune']}")

                if luogo["centralina"] == "Capannone 2":
                    righe_dispositivi.append("\t OZONEANDRIA006")
                    righe_dispositivi.append("\t OZONEANDRIA007")

                if luogo["centralina"] == "Capannone 1":
                    righe_dispositivi.append("\t OZONEANDRIA001")
                    righe_dispositivi.append("\t OZONEANDRIA002")
                    righe_dispositivi.append("\t OZONEANDRIA003")
                    righe_dispositivi.append("\t OZONEANDRIA004")
                    righe_dispositivi.append("\t OZONEANDRIA005")
            else:
                righe_dispositivi.append(
                    # dato il percorso define il luogo e lo zoom in cui rientra e il colore della legenda
                    f"- {info['ID']} - Centralina Mobile - {get_name_color(leg[info['ID']])}")
                print(
                    f"- {info['ID']} - Centralina Mobile - {get_name_color(leg[info['ID']])} - {leg[info['ID']]}")
        if proj["zoom"] == 4:
            righe_dispositivi.append(
                f"- {luogo['nazione']}, {luogo['regione']}, {luogo['squareID']}")
        if proj["zoom"] == 3:
            righe_dispositivi.append(
                f"- {luogo['nazione']}, {luogo['regione']}, {luogo['provincia']}, {luogo['comune']}")
        if proj["zoom"] == 2:
            righe_dispositivi.append(
                f"- {luogo['nazione']}, {luogo['regione']}, {luogo['provincia']}")
        if proj["zoom"] == 1:
            righe_dispositivi.append(
                f"- {luogo['nazione']}, {luogo['regione']}")
        if proj["zoom"] == 0:
            righe_dispositivi.append(f"- {luogo['nazione']}")

    # Crea il testo con l'elenco dei dispositivi
    elements.append(Paragraph(translation(
        LINGUA, "title_device"), heading_style))

    for riga in righe_dispositivi:
        elements.append(create_paragraph(riga, "normal_spaced"))

    elements.append(Paragraph("\n", normal_style))

    immagini = path_photos("mappa")

    elements.append(Paragraph("Mappe", heading_style))
    for immagine in immagini:
        print(immagine)
        # Aggiungi l'immagine al PDF
        elements.append(Image(immagine, width=430, height=200))
        if proj["zoom"] == 5:
            # scrivere una Caption con la città e il nome del sensore
            elements.append(create_paragraph(
                f"Mappa della città di {info_centralina(immagine.split('mappa_')[1].split('.')[0])['geodecode']['comune']} con la centralina {info_centralina(immagine.split('mappa_')[1].split('.')[0])['ID']}", "Caption"))
        elif proj["zoom"] == 4:
            elements.append(create_paragraph(
                f"Mappa della città di {immagine.split('_')[1].split('.')[0]}", "Caption"))
        elif proj["zoom"] == 3:
            elements.append(create_paragraph(
                f"Mappa della provincia di {immagine.split('_')[1].split('.')[0]}", "Caption"))
        elif proj["zoom"] == 2:
            elements.append(create_paragraph(
                f"Mappa della regione di {immagine.split('_')[1].split('.')[0]}", "Caption"))
        elif proj["zoom"] == 1:
            elements.append(create_paragraph(
                f"Mappa della nazione di {immagine.split('_')[1].split('.')[0]}", "Caption"))

        elements.append(Paragraph("\n", heading_style))

    # Crea il PDF
    document.build(elements)

    # Percorsi ai file
    background_pdf_path = f"{ABSOLUTE_PATH}/templates/Pagine_Example.pdf"
    content_pdf_path = f"{ABSOLUTE_PATH_REPORT}/Pagina_{proj['alias_progetto']}_Mappe.pdf"
    output_pdf_path = f"{ABSOLUTE_PATH_REPORT}/Pagina_{proj['alias_progetto']}_Mappe.pdf"

    # Unisci il PDF di sfondo con il PDF generato
    merge_pdfs_background(background_pdf_path,
                          content_pdf_path, output_pdf_path)


def genera_analisi_sforamenti(stile="Helvetica", x=30, y=770, cont=0, proj={}, freq="", title="", datainizio=None, datafine=None):

    if datainizio == None or datafine == None:
        datainizio, datafine = get_start_end_date(freq, proj)

    print("Analisi Sforamenti da ", datainizio, " a ", datafine)

    document = SimpleDocTemplate(
        f"{ABSOLUTE_PATH_REPORT}/{title}_Analisi.pdf", pagesize=A4)
    elements = []

    elements.append(Paragraph(f"Analisi Sforamenti", heading_style))

    for elem in proj["luoghi"]:
        if "centralina" in elem:
            elements.append(analisi_sforamenti(
                elem, datainizio, datafine, "hourly", 5, '["ssq"]', True))

    elements.append(Paragraph("\n", heading_style))
    elements.append(create_air_quality_table())

    # Crea il PDF
    document.build(elements)

    # Percorsi ai file
    background_pdf_path = f"{ABSOLUTE_PATH}/templates/Pagine_Example.pdf"
    content_pdf_path = f"{ABSOLUTE_PATH_REPORT}/{title}_Analisi.pdf"
    output_pdf_path = f"{ABSOLUTE_PATH_REPORT}/{title}_Analisi.pdf"

    # Unisci il PDF di sfondo con il PDF generato
    merge_pdfs_background(background_pdf_path,
                          content_pdf_path, output_pdf_path)

# creare una funzione che attraverso la funzione download_dati scarica i dati e se la frequenza è annuale analizza mese per mese i dati scaricati e conta quante volte i vari inquinanti superano il limite


def conteggio_sforamenti(places: dict, datainizio, datafine, progetto, zoo, freq, dati=False, pro=False):
    zoom = progetto["zoom"]
    for place in places:
        print(place)
       
        if all(k in place for k in ["nazione", "regione", "provincia", "comune", "centralina"]):
            id = str(place["centralina"]).upper()
        elif all(k in place for k in ["nazione", "regione", "provincia", "comune", "squareID"]):
            id = place["squareID"]
        elif all(k in place for k in ["nazione", "regione", "provincia", "comune"]):
            id = place["comune"]
        elif all(k in place for k in ["nazione", "regione", "provincia"]):
            id = place["provincia"]
        elif all(k in place for k in ["nazione", "regione"]):
            id = place["regione"]
        elif "nazione" in place:
            id = place["nazione"]
        else:
            id = None  # Valore di default se nessuna condizione è soddisfatta


        document = SimpleDocTemplate(
            f"{ABSOLUTE_PATH_REPORT}/{id}_Tabella_Analisi.pdf", pagesize=A4)
        elements = []
        type_dato = "hourly"

        if freq == "custom":
            datainizio, datafine = get_start_end_date(
                freq, pro=progetto, dati=True)
        else:
            datainizio, datafine = get_start_end_date(freq)

        print("Analisi Sforamenti da ", datainizio, " a ", datafine)

        dati = download_dati(place, datainizio, datafine, type_dato, zoom, "[]")

        # Converte lo stream di byte in un oggetto leggibile da Pandas
        csv_data = BytesIO(dati)

        try:
            # importare i dati in un dataframe tenendo conto che sono un csv sotto forma di stringa
            df = pd.read_csv(csv_data, sep=",")

            # print("Lunghezza dataframe: ", len(df))
            df_sforamenti = pd.DataFrame()

        except:
            print("Errore nel caricamento dei dati")
            print(format_exc())
            return

        # convertire la colonna timestamp in formato datetime partendo da questa stringa: 2024-01-02T19:00:00+0100
        df["timestamp"] = pd.to_datetime(
            df["timestamp"], format="%Y-%m-%dT%H:%M:%S%z", utc=True)

        # ordina i dati per il timestamp e stampa il primo timestamp
        df = df.sort_values(by="timestamp")
        print(df["timestamp"].iloc[0])

        # converti datainizio e datafine in formato datetime64 per fare il confronto con df["timestamp"] comparison between dtype=datetime64[ns, UTC] and datetime64
        datainizio_np = np.datetime64(datainizio)
        datafine_np = np.datetime64(datafine)

        df["timestamp"] = df["timestamp"].dt.tz_convert(None)

        # rimuovi i dati che non sono compresi tra datainizio e datafine
        df = df[(df["timestamp"] >= datainizio_np)
                & (df["timestamp"] <= datafine_np)]

        # se non ci sono dati che hanno come data di timestamp datainizio aggiungi una riga con i valori di default
        if len(df[df["timestamp"] == datainizio_np]) == 0:
            # non usare la funzione append
            df = pd.concat(
                [df, pd.DataFrame({"timestamp": [datainizio_np]})], ignore_index=True)

        # se non ci sono dati che hanno come data di timestamp datafine aggiungi una riga con i valori di default
        if len(df[df["timestamp"] == datafine_np]) == 0:
            # non usare la funzione append
            df = pd.concat(
                [df, pd.DataFrame({"timestamp": [datafine_np]})], ignore_index=True)

        print(df.dtypes)
        if freq == "annuali":
            # per ogni mese dell'anno contare quante volte i vari inquinanti superano il limite
            for mese in range(1, 13):
                df_mese = df[(df["timestamp"].dt.month == mese)]

                # print(f"Lunghezza dataframe mese {mese}: ", len(df_mese))

                for inquinante in df_mese.columns:
                    nome_inq = inquinante.split(" ")[0]

                    if nome_inq in nomi_inquinanti and nome_inq in limiti_inquinanti and nome_inq not in ["temperatura", "umidita"]:
                        count = len(df_mese[df_mese[inquinante] >
                                    limiti_inquinanti[nome_inq]])

                        df_sforamenti.at[mese,
                                         nomi_inquinanti[nome_inq]] = count

            # trasformare le colonne in int
            df_sforamenti = df_sforamenti.astype(int)

            # Crea una lista di righe per la tabella
            # Dati della tabella con Paragraph applicato
            data = []

            # inserire la prima riga in base alle colonne del dataframe df_sforamenti e aggiungendo i vari mesi
            header_table = [create_paragraph("Mese", 'Table Column')]
            for inquinante in df_sforamenti.columns:
                header_table.append(create_paragraph(
                    f"{inquinante} [-]", 'Table Column'))

            data.append(header_table)
            mesi_nomi = {1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile", 5: "Maggio", 6: "Giugno",
                         7: "Luglio", 8: "Agosto", 9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre"}
            for mese in range(1, 13):
                riga = [create_paragraph(str(mesi_nomi[mese]), 'Table Row')]
                for inquinante in df_sforamenti.columns:
                    riga.append(create_paragraph(
                        str(df_sforamenti.at[mese, inquinante]), 'Table Row'))

                data.append(riga)

            # sostiuisci il valore della cella della colonna mese con il suo nome
            df_sforamenti = df_sforamenti.rename(index=mesi_nomi)

            print(df_sforamenti)

            # in base al numero di righe creare un array per la dimensione dell'altezza della riga dove la prima riga è l'header che deve essere 30 e le altre 20
            altezze = [30]
            for i in range(1, len(data)):
                altezze.append(20)

            # Crea la tabella
            table = Table(data, rowHeights=altezze)

            # Applica lo stile alla tabella
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#009688")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))

            # Aggiungi la tabella al documento

            print("Analisi Sforamenti da ", datainizio, " a ", datafine)

            elements.append(
                Paragraph(f"Analisi dei dati di {id}", heading_style))
            elements.append(
                Paragraph("Tabella degli sforamenti", heading_style))

            elements.append(Paragraph("\n", heading_style))
            elements.append(table)

            # aggiungere una Caption sotto alla tabella
            elements.append(create_paragraph(
                "Tabella degli sforamenti: numero di superamenti delle soglie orarie per ciascun parametro monitorato, calcolati sulle medie orarie.", 'Caption'))

            if pro == True:
                try:
                    req = "Descrivi i vari sforamenti per ogni mese dando anche delle motivazioni non ripetendo le righe ma descrivendo solo che è successo nei mesi dell'anno in formato testo semplice come se lo scrivessi io, senza usare il grassetto\n" + df_sforamenti.to_string()

                    print(req)

                    resp = generate_text_sensesquare("llama3.2:3b", req)

                    elements.append(Paragraph(resp, normal_style))
                except:
                    req = "Descrivi i vari sforamenti per ogni mese dando anche delle motivazioni non ripetendo le righe ma descrivendo solo che è successo nei mesi dell'anno in formato testo semplice come se lo scrivessi io, senza usare il grassetto\n" + df_sforamenti.to_string()

                    model = genai.GenerativeModel("gemini-1.5-flash")
                    response = model.generate_content(req)

                    elements.append(Paragraph(response.text, normal_style))

            # creare una tabella con le medie stagionali degli inquinanti
            elements.append(
                Paragraph(f"Medie stagionali degli inquinanti", heading_style))

            # creare le medie stagionali inverno, primavera, estate, autunno evitando l'ID
            df_season = df.copy()

            df_season["timestamp"] = pd.to_datetime(
                df_season["timestamp"], format="%Y-%m-%dT%H:%M:%S%z", utc=True)

            df_season = df_season.select_dtypes(exclude=['object'])

            print(df_season.columns)

            df_season = df_season.groupby(
                df["timestamp"].dt.quarter).mean()  # escludi l'ID

            # Crea una lista di righe per la tabella
            # Dati della tabella con Paragraph applicato
            data = []

            df_season = df_season.drop("timestamp", axis=1)

            # se tutte le righe sono 0 cancellare le colonne
            for inquinante in df_season.columns:
                if df_season[inquinante].sum() == 0:
                    df_season = df_season.drop(inquinante, axis=1)

            # inserire la prima riga in base alle colonne del dataframe df_sforamenti e aggiungendo i vari mesi
            header_table = [create_paragraph("Stagione", 'Table Column')]
            for inquinante in df_season.columns:
                header_table.append(create_paragraph(
                    f"{nomi_inquinanti[inquinante.split(' ')[0]]}\n {inquinante.split(' ')[1]}", 'Table Column'))

            data.append(header_table)

            stagioni = {1: "Inverno", 2: "Primavera",
                        3: "Estate", 4: "Autunno"}

            # converti i campi in float e arrotonda alla seconda cifra decimale
            df_season = df_season.astype(float).round(2)

            for stagione in range(1, 5):

                riga = [create_paragraph(stagioni[stagione], 'Table Row')]
                for inquinante in df_season.columns:
                    riga.append(create_paragraph(
                        str(df_season.at[stagione, inquinante]), 'Table Row'))

                data.append(riga)

            # sostiuisci il valore della cella della colonna mese con il suo nome
            df_season = df_season.rename(index=stagioni)

            altezze = [30]
            for i in range(1, len(data)):
                altezze.append(20)

            table_season = Table(data, rowHeights=altezze)

            # Applica lo stile alla tabella e metterne uno spazio sotto la tabella per la Caption
            table_season.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#009688")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))

            elements.append(Paragraph("\n", heading_style))
            elements.append(table_season)
            elements.append(create_paragraph(
                "Tabella delle medie stagionali degli inquinanti: medie stagionali degli inquinanti monitorati, calcolati sulle medie orarie.", 'Caption'))

            if pro == True:
                try:
                    req = "Descrivi le medie stagionali degli inquinanti per ogni stagione dando anche delle motivazioni non ripetendo le righe ma descrivendo solo che è successo nelle stagioni dell'anno in formato testo semplice come se lo scrivessi io, senza usare il grassetto\n" + df_season.to_string()

                    response = generate_text_sensesquare("llama3.2:3b", req)

                    elements.append(Paragraph(response, normal_style))
                except:
                    req = "Descrivi le medie stagionali degli inquinanti per ogni stagione dando anche delle motivazioni non ripetendo le righe ma descrivendo solo che è successo nelle stagioni dell'anno in formato testo semplice come se lo scrivessi io, senza usare il grassetto\n" + df_season.to_string()

                    model = genai.GenerativeModel("gemini-1.5-flash")
                    response = model.generate_content(req)

                    elements.append(Paragraph(response.text, normal_style))

            # creare una tabella con le medie semestrali
            elements.append(
                Paragraph(f"Medie semestrali degli inquinanti", heading_style))

            df_semester = df.copy()

            df_semester["timestamp"] = pd.to_datetime(
                df_semester["timestamp"], format="%Y-%m-%dT%H:%M:%S%z", utc=True)

            df_semester = df_semester.select_dtypes(exclude=['object'])

            # fai le medie dei primi due trimestri e degli ultimi due trimestri
            df_semester = df_semester.groupby(
                df["timestamp"].dt.quarter // 2).mean()

            # Crea una lista di righe per la tabella
            # Dati della tabella con Paragraph applicato
            data = []

            df_semester = df_semester.drop("timestamp", axis=1)

            # se tutte le righe sono 0 cancellare le colonne
            for inquinante in df_semester.columns:
                if df_semester[inquinante].sum() == 0:
                    df_semester = df_semester.drop(inquinante, axis=1)

            # inserire la prima riga in base alle colonne del dataframe df_sforamenti e aggiungendo i vari mesi
            header_table = [create_paragraph("Semestre", 'Table Column')]

            for inquinante in df_semester.columns:
                header_table.append(create_paragraph(
                    f"{nomi_inquinanti[inquinante.split(' ')[0]]}\n {inquinante.split(' ')[1]}", 'Table Column'))

            data.append(header_table)

            semestri = {0: "Primo Semestre", 1: "Secondo Semestre"}

            # converti i campi in float e arrotonda alla seconda cifra decimale

            df_semester = df_semester.astype(float).round(2)

            for semestre in range(0, 2):

                riga = [create_paragraph(semestri[semestre], 'Table Row')]
                for inquinante in df_semester.columns:
                    riga.append(create_paragraph(
                        str(df_semester.at[semestre, inquinante]), 'Table Row'))

                data.append(riga)

            altezze = [30]

            for i in range(1, len(data)):
                altezze.append(20)

            table_semester = Table(data, rowHeights=altezze)

            # Applica lo stile alla tabella e metterne uno spazio sotto la tabella per la Caption

            table_semester.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#009688")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))

            elements.append(Paragraph("\n", heading_style))

            elements.append(table_semester)

            elements.append(create_paragraph(
                "Tabella delle medie semestrali degli inquinanti: medie semestrali degli inquinanti monitorati, calcolati sulle medie orarie.", 'Caption'))

            if pro == True:
                try:
                    req = "Descrivi le medie semestrali degli inquinanti per ogni semestre dando anche delle motivazioni non ripetendo le righe ma descrivendo solo che è successo nei semestri dell'anno in formato testo semplice come se lo scrivesi io, senza usare il grassetto\n" + df_semester.to_string()
                    response = generate_text_sensesquare("llama3.2:3b", req)

                    elements.append(Paragraph(response, normal_style))
                except:
                    req = "Descrivi le medie semestrali degli inquinanti per ogni semestre dando anche delle motivazioni non ripetendo le righe ma descrivendo solo che è successo nei semestri dell'anno in formato testo semplice come se lo scrivessi io, senza usare il grassetto\n" + df_semester.to_string()
                    model = genai.GenerativeModel("gemini-1.5-flash")
                    response = model.generate_content(req)

                    elements.append(Paragraph(response.text, normal_style))

        if freq == "mensili":
            # per ogni giorno del mese contare quante volte i vari inquinanti superano il limite
            for giorno in range(1, 32):
                df_giorno = df[(df["timestamp"].dt.day == giorno)]

                # print(f"Lunghezza dataframe giorno {giorno}: ", len(df_giorno))

                for inquinante in df_giorno.columns:
                    nome_inq = inquinante.split(" ")[0]

                    if nome_inq in nomi_inquinanti and nome_inq in limiti_inquinanti and nome_inq not in ["temperatura", "umidita"]:
                        count = len(df_giorno[df_giorno[inquinante] >
                                    limiti_inquinanti[nome_inq]])

                        df_sforamenti.at[giorno,
                                         nomi_inquinanti[nome_inq]] = count

            # trasformare le colonne in int

            df_sforamenti = df_sforamenti.astype(int)

            # Crea una lista di righe per la tabella
            # Dati della tabella con Paragraph applicato
            data = []

            # inserire la prima riga in base alle colonne del dataframe df_sforamenti e aggiungendo i vari mesi
            header_table = [create_paragraph("Giorno", 'Table Column')]
            for inquinante in df_sforamenti.columns:
                header_table.append(create_paragraph(
                    f"{inquinante} [-]", 'Table Column'))

            data.append(header_table)

            for giorno in range(1, len(df_sforamenti) + 1):
                riga = [create_paragraph(str(giorno), 'Table Row')]
                for inquinante in df_sforamenti.columns:
                    riga.append(create_paragraph(
                        str(df_sforamenti.at[giorno, inquinante]), 'Table Row'))

                data.append(riga)

            altezze = [30]
            for i in range(1, len(data)):
                altezze.append(15)

            # Crea la tabella
            table = Table(data, rowHeights=altezze)

            # Applica lo stile alla tabella
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#009688")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))

            # Aggiungi la tabella al documento

            print("Analisi Sforamenti da ", datainizio, " a ", datafine)

            document = SimpleDocTemplate(
                f"{ABSOLUTE_PATH_REPORT}/{id}_Tabella_Analisi.pdf", pagesize=A4)
            elements = []

            elements.append(
                Paragraph(f"Analisi dei dati di {id}", heading_style))
            elements.append(
                Paragraph("Tabella degli sforamenti", heading_style))

            elements.append(Paragraph("\n", heading_style))
            elements.append(table)

            # aggiungere una Caption sotto alla tabella
            elements.append(create_paragraph(
                "Tabella degli sforamenti: numero di superamenti delle soglie orarie per ciascun parametro monitorato, calcolati sulle medie orarie.", 'Caption'))

            if pro == True:
                try:
                    req = "Descrivi i vari sforamenti per ogni giorno dando anche delle motivazioni non ripetendo le righe ma descrivendo solo che è successo nei giorni del mese in formato testo semplice come se lo scrivessi io, senza usare il grassetto\n" + df_sforamenti.to_string()

                    response = generate_text_sensesquare("llama3.2:3b", req)

                    elements.append(Paragraph(response, normal_style))
                except:
                    req = "Descrivi i vari sforamenti per ogni giorno dando anche delle motivazioni non ripetendo le righe ma descrivendo solo che è successo nei giorni del mese in formato testo semplice come se lo scrivessi io, senza usare il grassetto\n" + df_sforamenti.to_string()

                    model = genai.GenerativeModel("gemini-1.5-flash")
                    response = model.generate_content(req)

                    elements.append(Paragraph(response.text, normal_style))

            # creare una tabella con le medie settimanali
            elements.append(
                Paragraph(f"Medie settimanali degli inquinanti", heading_style))

            df_week = df.copy()

            df_week["timestamp"] = pd.to_datetime(
                df_week["timestamp"], format="%Y-%m-%dT%H:%M:%S%z", utc=True)

            #cancella le colonne che sono di tipo object
            df_week = df_week.select_dtypes(exclude=['object'])

            # crea le medie sui range di 7 giorni

            df_week["timestamp"] = pd.to_datetime(
                df_week["timestamp"], utc=True)
            df_week = df_week.set_index("timestamp")

            df_week = df_week.resample("7D").mean().reset_index()

            # scrivere i range di date in cui si è diviso il dataframe

            print(df_week["timestamp"])

            # Crea una lista di righe per la tabella
            # Dati della tabella con Paragraph applicato

            data = []

            df_week = df_week.drop("timestamp", axis=1)

            # creare un dizionario dove per ogni numero di settimana presente nel df_week corrisponde una stringa con la data di inizio e di fine della settimana
            settimane = {}
            for i in df_week.index:
                if datainizio + timedelta(days=(i+1)*7) > datafine:
                    settimane[i] = f"{(datainizio + timedelta(days=i*7)).strftime('%d/%m/%Y')} - {datafine.strftime('%d/%m/%Y')}"
                else:
                    settimane[i] = f"{(datainizio + timedelta(days=i*7)).strftime('%d/%m/%Y')} - {(datainizio + timedelta(days=(i+1)*7)).strftime('%d/%m/%Y')}"

            print(settimane)

            # sostituire i valori dell'index con i valori del dizionario settimane
            df_week = df_week.rename(index=settimane)

            df_week = df_week.astype(float).round(2)
            # se tutte le righe sono 0 cancellare le colonne

            for inquinante in df_week.columns:
                if df_week[inquinante].sum() == 0:
                    df_week = df_week.drop(inquinante, axis=1)

            # inserire la prima riga in base alle colonne del dataframe df_sforamenti e aggiungendo i vari mesi
            header_table = [create_paragraph("Settimana", 'Table Column')]
            for inquinante in df_week.columns:
                header_table.append(create_paragraph(
                    f"{nomi_inquinanti[inquinante.split(' ')[0]]}\n {inquinante.split(' ')[1]}", 'Table Column'))

            data.append(header_table)

            # stampare le settimane presenti nel dataframe
            print(df_week.index)

            for settimana in df_week.index:
                riga = [create_paragraph(str(settimana), 'Table Row')]
                for inquinante in df_week.columns:
                    riga.append(create_paragraph(
                        str(df_week.at[settimana, inquinante]), 'Table Row'))

                data.append(riga)

            altezze = [30]
            for i in range(1, len(data)):
                altezze.append(20)

            # Crea la tabella
            table = Table(data, rowHeights=altezze)

            # Applica lo stile alla tabella
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#009688")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))

            # Aggiungi la tabella al documento

            print("Analisi Sforamenti da ", datainizio, " a ", datafine)

            elements.append(table)

            # aggiungere una Caption sotto alla tabella
            elements.append(create_paragraph(
                "Tabella delle medie settimanali degli inquinanti: medie settimanali degli inquinanti monitorati, calcolati sulle medie orarie.", 'Caption'))

            if pro == True:
                try:
                    req = "Descrivi le medie settimanali degli inquinanti per ogni settimana dando anche delle motivazioni non ripetendo le righe ma descrivendo solo che è successo nelle settimane del mese in formato testo semplice come se lo scrivessi io, senza usare il grassetto\n" + df_week.to_string()

                    response = generate_text_sensesquare("llama3.2:3b", req)

                    elements.append(Paragraph(response, normal_style))
                except:
                    req = "Descrivi le medie settimanali degli inquinanti per ogni settimana dando anche delle motivazioni non ripetendo le righe ma descrivendo solo che è successo nelle settimane del mese in formato testo semplice come se lo scrivessi io, senza usare il grassetto\n" + df_week.to_string()

                    model = genai.GenerativeModel("gemini-1.5-flash")
                    response = model.generate_content(req)

                    elements.append(Paragraph(response.text, normal_style))

        if freq == "giornalieri":
            # per ogni ora del giorno contare quante volte i vari inquinanti superano il limite
            for ora in range(0, 24):
                df_ora = df[(df["timestamp"].dt.hour == ora)]

                # print(f"Lunghezza dataframe ora {ora}: ", len(df_ora))

                for inquinante in df_ora.columns:
                    nome_inq = inquinante.split(" ")[0]

                    if nome_inq in nomi_inquinanti and nome_inq in limiti_inquinanti and nome_inq not in ["temperatura", "umidita"]:
                        count = len(df_ora[df_ora[inquinante] >
                                    limiti_inquinanti[nome_inq]])

                        df_sforamenti.at[ora,
                                         nomi_inquinanti[nome_inq]] = count

            # trasformare le colonne in int

            df_sforamenti = df_sforamenti.astype(int)

            # Crea una lista di righe per la tabella

            # Dati della tabella con Paragraph applicato
            data = []

            # inserire la prima riga in base alle colonne del dataframe df_sforamenti e aggiungendo i vari mesi
            header_table = [create_paragraph("Ora", 'Table Column')]
            for inquinante in df_sforamenti.columns:
                header_table.append(create_paragraph(
                    f"{inquinante} [-]", 'Table Column'))

            data.append(header_table)

            for ora in range(0, len(df_sforamenti)):
                riga = [create_paragraph(f"{ora}:00", 'Table Row')]
                for inquinante in df_sforamenti.columns:
                    riga.append(create_paragraph(
                        str(df_sforamenti.at[ora, inquinante]), 'Table Row'))

                data.append(riga)

            altezze = [30]
            for i in range(1, len(data)):
                altezze.append(20)

            # Crea la tabella
            table = Table(data, rowHeights=altezze)

            # Applica lo stile alla tabella
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#009688")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))

            # Aggiungi la tabella al documento
            elements.append(
                Paragraph(f"Analisi dei dati di {id}", heading_style))

            elements.append(
                Paragraph("Tabella degli sforamenti", heading_style))

            elements.append(Paragraph("\n", heading_style))

            elements.append(table)

            # aggiungere una Caption sotto alla tabella

            elements.append(create_paragraph(
                "Tabella degli sforamenti: numero di superamenti delle soglie orarie per ciascun parametro monitorato, calcolati sulle medie orarie.", 'Caption'))

            if pro == True:
                try:
                    req = "Descrivi i vari sforamenti per ogni ora del giorno dando anche delle motivazioni non ripetendo le righe ma descrivendo solo che è successo nelle ore del giorno in formato testo semplice come se lo scrivessi io, senza usare il grassetto\n" + df_sforamenti.to_string()

                    response = generate_text_sensesquare("llama3.2:3b", req)

                    elements.append(Paragraph(response, normal_style))
                except:
                    req = "Descrivi i vari sforamenti per ogni ora del giorno dando anche delle motivazioni non ripetendo le righe ma descrivendo solo che è successo nelle ore del giorno in formato testo semplice come se lo scrivessi io, senza usare il grassetto\n" + df_sforamenti.to_string()

                    model = genai.GenerativeModel("gemini-1.5-flash")
                    response = model.generate_content(req)

                    elements.append(Paragraph(response.text, normal_style))

            # creare una tabella con le medie dividendo il giorno di 24 ore in 4 parti
            elements.append(
                Paragraph(f"Medie nel corso della giornata degli inquinanti", heading_style))

            df_day = df.copy()

            df_day["timestamp"] = pd.to_datetime(
                df_day["timestamp"], format="%Y-%m-%dT%H:%M:%S%z", utc=True)

            df_day = df_day.select_dtypes(exclude=['object'])

            # crea le medie sui range di 6 ore

            df_day["timestamp"] = pd.to_datetime(df_day["timestamp"], utc=True)
            df_day = df_day.set_index("timestamp")

            df_day = df_day.resample("6h").mean().reset_index()

            # scrivere i range di date in cui si è diviso il dataframe

            print(df_day["timestamp"])

            # Crea una lista di righe per la tabella
            # Dati della tabella con Paragraph applicato

            data = []

            df_day = df_day.drop("timestamp", axis=1)

            # creare un dizionario dove per ogni numero di settimana presente nel df_week corrisponde una stringa con la data di inizio e di fine della settimana
            ore = {}
            for i in df_day.index:
                if datainizio + timedelta(hours=(i+1)*6) > datafine:
                    ore[i] = f"{(datainizio + timedelta(hours=i*6)).strftime('%H:%M')} - {datafine.strftime('%H:%M')}"
                else:
                    ore[i] = f"{(datainizio + timedelta(hours=i*6)).strftime('%H:%M')} - {(datainizio + timedelta(hours=(i+1)*6)).strftime('%H:%M')}"

            print(ore)

            # sostituire i valori dell'index con i valori del dizionario settimane
            df_day = df_day.rename(index=ore)

            df_day = df_day.astype(float).round(2)

            # se tutte le righe sono 0 cancellare le colonne

            for inquinante in df_day.columns:
                if df_day[inquinante].sum() == 0:
                    df_day = df_day.drop(inquinante, axis=1)

            # inserire la prima riga in base alle colonne del dataframe df_sforamenti e aggiungendo i vari mesi
            header_table = [create_paragraph("Ora", 'Table Column')]

            for inquinante in df_day.columns:
                header_table.append(create_paragraph(
                    f"{nomi_inquinanti[inquinante.split(' ')[0]]}\n {inquinante.split(' ')[1]}", 'Table Column'))

            data.append(header_table)

            # stampare le settimane presenti nel dataframe
            print(df_day.index)

            for ora in df_day.index:
                riga = [create_paragraph(ora, 'Table Row')]
                for inquinante in df_day.columns:
                    riga.append(create_paragraph(
                        str(df_day.at[ora, inquinante]), 'Table Row'))

                data.append(riga)

            altezze = [30]

            for i in range(1, len(data)):
                altezze.append(20)

            # Crea la tabella
            table = Table(data, rowHeights=altezze)

            # Applica lo stile alla tabella
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#009688")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))

            # Aggiungi la tabella al documento

            elements.append(table)

            # aggiungere una Caption sotto alla tabella
            elements.append(create_paragraph(
                "Tabella delle medie nel corso della giornata degli inquinanti: medie orarie degli inquinanti monitorati, calcolati sulle medie orarie.", 'Caption'))

            if pro == True:
                try:
                    req = "Descrivi le medie nel corso della giornata degli inquinanti per ogni ora del giorno dando anche delle motivazioni non ripetendo le righe ma descrivendo solo che è successo nelle ore del giorno in formato testo semplice come se lo scrivessi io, senza usare il grassetto\n" + df_day.to_string()

                    response = generate_text_sensesquare("llama3.2:3b", req)

                    elements.append(Paragraph(response, normal_style))
                except:
                    req = "Descrivi le medie nel corso della giornata degli inquinanti per ogni ora del giorno dando anche delle motivazioni non ripetendo le righe ma descrivendo solo che è successo nelle ore del giorno in formato testo semplice come se lo scrivessi io, senza usare il grassetto\n" + df_day.to_string()

                    model = genai.GenerativeModel("gemini-1.5-flash")
                    response = model.generate_content(req)

                    elements.append(Paragraph(response.text, normal_style))

        if freq == "settimanali":
            # per ogni giorno della settimana contare quante volte i vari inquinanti superano il limite
            for giorno in range(0, 7):
                df_giorno = df[(df["timestamp"].dt.dayofweek == giorno)]

                # print(f"Lunghezza dataframe giorno {giorno}: ", len(df_giorno))

                for inquinante in df_giorno.columns:
                    nome_inq = inquinante.split(" ")[0]

                    if nome_inq in nomi_inquinanti and nome_inq in limiti_inquinanti and nome_inq not in ["temperatura", "umidita"]:
                        count = len(df_giorno[df_giorno[inquinante] >
                                    limiti_inquinanti[nome_inq]])

                        df_sforamenti.at[giorno,
                                         nomi_inquinanti[nome_inq]] = count

            # trasformare le colonne in int

            df_sforamenti = df_sforamenti.astype(int)

            # Crea una lista di righe per la tabella
            # Dati della tabella con Paragraph applicato
            data = []

            # inserire la prima riga in base alle colonne del dataframe df_sforamenti e aggiungendo i vari mesi
            header_table = [create_paragraph(
                "Giorno della settimana", 'Table Column')]
            for inquinante in df_sforamenti.columns:
                header_table.append(create_paragraph(
                    f"{inquinante} [-]", 'Table Column'))

            data.append(header_table)

            giorni_settimana = {0: "Lunedì", 1: "Martedì",
                                2: "Mercoledì", 3: "Giovedì", 4: "Venerdì", 5: "Sabato", 6: "Domenica"}

            # sostituire i valori dell'index con i nomi dei giorni della settimana
            df_sforamenti = df_sforamenti.rename(index=giorni_settimana)

            for giorno in df_sforamenti.index:
                riga = [create_paragraph(str(giorno), 'Table Row')]
                for inquinante in df_sforamenti.columns:
                    riga.append(create_paragraph(
                        str(df_sforamenti.at[giorno, inquinante]), 'Table Row'))

                data.append(riga)

            altezze = [30]
            for i in range(1, len(data)):
                altezze.append(20)

            # Crea la tabella
            table = Table(data, rowHeights=altezze)

            # Applica lo stile alla tabella
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#009688")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))

            # Aggiungi la tabella al documento

            elements.append(
                Paragraph(f"Analisi dei dati di {id}", heading_style))

            elements.append(
                Paragraph("Tabella degli sforamenti", heading_style))

            elements.append(Paragraph("\n", heading_style))

            elements.append(table)

            # aggiungere una Caption sotto alla tabella

            elements.append(create_paragraph(
                "Tabella degli sforamenti: numero di superamenti delle soglie orarie per ciascun parametro monitorato, calcolati sulle medie orarie.", 'Caption'))

            if pro == True:
                try:
                    req = "Descrivi i vari sforamenti per ogni giorno della settimana dando anche delle motivazioni non ripetendo le righe ma descrivendo solo che è successo nei giorni della settimana in formato testo semplice come se lo scrivessi io, senza usare il grassetto\n" + df_sforamenti.to_string()

                    response = generate_text_sensesquare("llama3.2:3b", req)

                    elements.append(Paragraph(response, normal_style))
                except:
                    req = "Descrivi i vari sforamenti per ogni giorno della settimana dando anche delle motivazioni non ripetendo le righe ma descrivendo solo che è successo nei giorni della settimana in formato testo semplice come se lo scrivessi io, senza usare il grassetto\n" + df_sforamenti.to_string()

                    model = genai.GenerativeModel("gemini-1.5-flash")
                    response = model.generate_content(req)

                    elements.append(Paragraph(response.text, normal_style))

            # creare le medie per i giorni lavorativi e non lavorativi
            elements.append(
                Paragraph(f"Medie per giorni lavorativi e non lavorativi", heading_style))

            df_weekday = df.copy()

            df_weekday["timestamp"] = pd.to_datetime(
                df_weekday["timestamp"], format="%Y-%m-%dT%H:%M:%S%z", utc=True)

            df_weekday = df_weekday.select_dtypes(exclude=['object'])

            # crea le medie per i giorni lavorativi e non lavorativi

            df_weekday["timestamp"] = pd.to_datetime(
                df_weekday["timestamp"], utc=True)
            df_weekday = df_weekday.set_index("timestamp")

            df_weekday["weekday"] = df_weekday.index.weekday

            df_weekday["weekday"] = df_weekday["weekday"].apply(
                lambda x: "Festivo" if x > 4 else "Lavorativo")

            df_weekday = df_weekday.groupby("weekday").mean()

            # arrotonda i valori a due cifre decimali
            df_weekday = df_weekday.astype(float).round(2)

            # Crea una lista di righe per la tabella
            # Dati della tabella con Paragraph applicato

            data = []
            # se tutte le righe sono 0 cancellare le colonne
            #
            # inserire la prima riga in base alle colonne del dataframe df_sforamenti e aggiungendo i vari mesi

            header_table = [create_paragraph("Giorno", 'Table Column')]
            for inquinante in df_weekday.columns:
                header_table.append(create_paragraph(
                    f"{nomi_inquinanti[inquinante.split(' ')[0]]}\n {inquinante.split(' ')[1]}", 'Table Column'))

            data.append(header_table)

            for giorno in df_weekday.index:
                riga = [create_paragraph(giorno, 'Table Row')]
                for inquinante in df_weekday.columns:
                    riga.append(create_paragraph(
                        str(df_weekday.at[giorno, inquinante]), 'Table Row'))

                data.append(riga)

            altezze = [30]
            for i in range(1, len(data)):
                altezze.append(20)

            # Crea la tabella
            table = Table(data, rowHeights=altezze)

            # Applica lo stile alla tabella

            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#009688")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))

            # Aggiungi la tabella al documento
            elements.append(table)

            # aggiungere una Caption sotto alla tabella
            elements.append(create_paragraph(
                "Tabella delle medie per giorni lavorativi e non lavorativi degli inquinanti: medie orarie degli inquinanti monitorati, calcolati sulle medie orarie.", 'Caption'))

            if pro == True:
                try:
                    req = "Descrivi le medie per giorni lavorativi e non lavorativi degli inquinanti dando anche delle motivazioni non ripetendo le righe ma descrivendo solo che è successo nei giorni lavorativi e non lavorativi in formato testo semplice come se lo scrivessi io, senza usare il grassetto\n" + df_weekday.to_string()

                    response = generate_text_sensesquare("llama3.2:3b", req)

                    elements.append(Paragraph(response, normal_style))
                except:
                    req = "Descrivi le medie per giorni lavorativi e non lavorativi degli inquinanti dando anche delle motivazioni non ripetendo le righe ma descrivendo solo che è successo nei giorni lavorativi e non lavorativi in formato testo semplice come se lo scrivessi io, senza usare il grassetto\n" + df_weekday.to_string()

                    model = genai.GenerativeModel("gemini-1.5-flash")
                    response = model.generate_content(req)

                    elements.append(Paragraph(response.text, normal_style))

        elements.append(Paragraph("Tabella riepitologativa degli inquinanti", heading_style))

        data = [
            [create_paragraph('Inquinante','Table Column'), create_paragraph('Descrizione','Table Column'), create_paragraph(
                'Unità di misura','Table Column'), create_paragraph('Intervallo di valutazione','Table Column'), create_paragraph('Valore limite','Table Column')],
            [create_paragraph('NO2','Table Row'), create_paragraph('Biossido di azoto','Table Row'), create_paragraph('µg/m³','Table Row'), create_paragraph(
                'massima media oraria','Table Row'), create_paragraph('Il valore orario di 200 µg/m³ non può essere superato più di 18 volte nell\'anno','Table Row')],
            [create_paragraph('CO','Table Row'), create_paragraph('Monossido di carbonio','Table Row'), create_paragraph('mg/m³','Table Row'), create_paragraph(
                'massima media oraria','Table Row'), create_paragraph('Il valore massimo della media mobile calcolata sulle 8 ore non può superare i 10 mg/m³','Table Row')],
            [create_paragraph('PM10','Table Row'), create_paragraph('Polveri sospese minori di 10µm','Table Row'), create_paragraph('µg/m³','Table Row'), create_paragraph(
                'media giornaliera','Table Row'), create_paragraph('Il valore giornaliero di 50 µg/m³ non può essere superato più di 35 volte nell\'anno','Table Row')],
            [create_paragraph('PM2.5','Table Row'), create_paragraph('Polveri sospese minori di 2,5µm','Table Row'), create_paragraph(
                'µg/m³','Table Row'), create_paragraph('media annuale','Table Row'), create_paragraph('Il valore medio annuale di 25 µg/m³ non può essere superato nell\'anno','Table Row')],
            [create_paragraph('O3','Table Row'), create_paragraph('Ozono','Table Row'), create_paragraph('µg/m³','Table Row'), create_paragraph('massima media oraria','Table Row'),
             create_paragraph('Il valore orario della soglia di informazione è pari a 180 µg/m³. La soglia di allarme è pari a 240 µg/m³','Table Row')],
            [create_paragraph('C6H6','Table Row'), create_paragraph('Benzene','Table Row'), create_paragraph('µg/m³','Table Row'), create_paragraph(
                'media annuale','Table Row'), create_paragraph('Il valore medio annuale di 5 µg/m³ non può essere superato nell\'anno','Table Row')],
            [create_paragraph('SO2','Table Row'), create_paragraph('Biossido di zolfo','Table Row'), create_paragraph('µg/m³','Table Row'), create_paragraph(
                'massima media oraria','Table Row'), create_paragraph('Il valore orario di 350 µg/m³ non può essere superato più di 24 volte nell\'anno','Table Row')],
        ]

        # Definisci larghezze delle colonne proporzionate per A4 verticale
        #col_widths = [80, 70, 60, 70, 155]  # Regola le larghezze
        col_widths = [65, 70, 60, 70, 175]
        # Altezza fissa per le righe dei dati
        row_heights = [30] + [50] * (len(data) - 1)

        # Crea la tabella e specifica larghezze delle colonne e altezze delle righe
        table = Table(data, rowHeights=row_heights, colWidths=col_widths)

        # Applica lo stile alla tabella
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#009688")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))

        # Aggiungi la tabella al documento
        elements.append(table)

        # Crea il PDF
        document.build(elements)

        # Percorsi ai file
        background_pdf_path = f"{ABSOLUTE_PATH}/templates/Pagine_Example.pdf"
        content_pdf_path = f"{ABSOLUTE_PATH_REPORT}/{id}_Tabella_Analisi.pdf"
        output_pdf_path = f"{ABSOLUTE_PATH_REPORT}/{id}_Tabella_Analisi.pdf"

        # Unisci il PDF di sfondo con il PDF generato
        merge_pdfs_background(background_pdf_path,
                              content_pdf_path, output_pdf_path)


def generate_comments(places: dict, zoo, freq):
    openai.api_key = os.getenv("OPENAI_API_KEY")
    zoo_luogo = {"0": "la Nazione", "1": "la Regione", "2": "la Provincia",
                 "3": "il Comune", "4": "lo squareID", "5": "la Centralina"}
    limiti = {"PM10": 50, "PM2.5": 25, "NO2": 200,
              "O3": 120, "SO2": 350, "CO": 10, "AQI": 100}
    unita_misura = {"PM10": "µg/m³", "PM2.5": "µg/m³", "NO2": "µg/m³", "O3": "µg/m³",
                    "SO2": "µg/m³", "CO": "mg/m³", "AQI": "%", "PM1": "µg/m³", "Temperatura": "°C", "Umidità": "%"}

    if freq == "giornalieri":
        type = "hourly"
    else:
        type = "daily"

    prompt = f"Puoi generare un commento sui valori rilevati dal{zoo_luogo[zoo]}. Evitando di ripetere tutti i valori rilevati dal{zoo_luogo[zoo]}, puoi concentrarti su quelli più importanti."
    info = ""
    if zoo == "5":
        info = info_centralina(places[0]["centralina"])
        prompt += f"\n\nLa centralina si trova nella città di {info['geodecode']['comune']} "

        if "indirizzo" in info:
            prompt += f"in via {info['indirizzo']}."
        else:
            prompt += "."

    if freq == "custom":
        datainizio, datafine = get_start_end_date(freq, dati=True)
    else:
        datainizio, datafine = get_start_end_date(freq)
    dati = download_dati(places[0], datainizio, datafine, type, zoo, "[]")

    # Converte lo stream di byte in un oggetto leggibile da Pandas
    csv_data = BytesIO(dati)

    # importare i dati in un dataframe tenendo conto che sono un csv sotto forma di stringa
    df = pd.read_csv(csv_data, sep=",")

    prompt += "\n\n"
    prompt += "I limiti di legge per gli inquinanti sono:\n"
    # per ogni inquinante che sta nelle colonne di df metto il limite se è presente nel dizionario limiti
    for inquinante in df.columns:
        if inquinante in nomi_inquinanti and nomi_inquinanti[inquinante] in limiti:
            prompt += f"{nomi_inquinanti[inquinante]}: {limiti[nomi_inquinanti[inquinante]]} {unita_misura[nomi_inquinanti[inquinante]]}\n"
    prompt += f"Le unità di misura sono: \n"
    # per ogni inquinante che sta nelle colonne di df metto l'unità di misura se è presente nel dizionario unita_misura
    for inquinante in df.columns:
        if inquinante in nomi_inquinanti and nomi_inquinanti[inquinante] in limiti:
            prompt += f"{nomi_inquinanti[inquinante]}: {unita_misura[nomi_inquinanti[inquinante]]}\n"
    prompt += "\n\n"
    prompt += df.to_string(index=False)
    prompt += "\n\n"

    prompt += "I valori degli anni scorsi sono stati:\n"

    dati = download_dati(places[0], datainizio - timedelta(days=365),
                         datafine - timedelta(days=365), type, zoo, "[]")

    # Converte lo stream di byte in un oggetto leggibile da Pandas
    csv_data = BytesIO(dati)

    # importare i dati in un dataframe tenendo conto che sono un csv sotto forma di stringa
    df = pd.read_csv(csv_data, sep=",")

    prompt += df.to_string(index=False)

    prompt += "\n\n"
    print(prompt)
    chat_completion = openai.ChatCompletion.create(
        # Imposta il numero massimo di token per la risposta
        model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}],
        temperature=0.5)

    return chat_completion["choices"][0]["message"]["content"]


def aggiungi_Commenti(pdf, stile, x, y, width, height, data, f):
    # Inizia stampando "Commenti:" e va a capo
    pdf.setFont(stile, 17)
    pdf.drawString(x, y, "Commenti:")
    y -= 20  # Spostamento verticale per andare a capo
    # con questo cont aggiungo il testo numerato
    cont = 1
    testo = ""
    pro = False
    if pro:
        testo = generate_comments(data["luoghi"], "5", f)

    testo_formattato = ""
    # qui formatto il testo
    for line in testo.splitlines():
        if line.startswith(str(cont) + ". "):
            cont += 1
        testo_formattato += line + " "
    righe = []
    riga_corrente = " "
    for parola in testo_formattato.split():
        parola_corrente = riga_corrente + parola + " "
        if pdf.stringWidth(parola_corrente, stile, 12.5) <= width - x-10:
            riga_corrente = parola_corrente
        else:
            righe.append(riga_corrente)
            riga_corrente = parola + " "
    righe.append(riga_corrente)

    # Stampa le righe sulla pagina
    for riga in righe:
        pdf.setFont(stile, 12)
        # Allinea il testo all'inizio della pagina a sinistra
        pdf.drawString(x, y, riga)
        y -= 20  # Spostamento verticale per la riga successiva

        # Vai a capo se si raggiunge la fine della pagina
        if y < 50:
            pdf.showPage()  # Nuova pagina
            pdf.drawImage(lista_template[1], 0, 0, width, height)
            FrameFooter(pdf, stile)
            y = 800  # Reset della posizione verticale

    return x, y


def add_title_foto(pdf, x, y, width, height, stile, title=None, subtitle=None, type=None, inq=""):
    default_title = ""

    # Predefined title
    if type == "mappa":
        default_title = translation(LINGUA, "map")
    else:
        default_title = f"{translation(LINGUA, 'graph_view')} {inq}"

    if subtitle is None:
        subtitle = " "  # Leave as an empty string or change to a default subtitle if neede
    # Combine the default title with the specific title (if available)
    full_title = f"{default_title}:"

    pdf.setFont(stile, 15)
    pdf.drawString(x, y, full_title)  # Use the combined title
    y -= 15  # Spostamento verticale per andare a capo

    righe = []
    riga_corrente = ""
    riga_corrente_dispositivi = ""  # Initialize the variable

    for parola in subtitle.split():
        parola_corrente = riga_corrente + parola + " "
        if pdf.stringWidth(parola_corrente, stile, 12) <= width - x:
            riga_corrente_dispositivi = parola_corrente
        else:
            righe.append(riga_corrente_dispositivi)
            riga_corrente_dispositivi = parola + " "
    righe.append(riga_corrente_dispositivi)

    # Stampa le righe dell'elenco dispositivi sulla pagina
    for riga in righe:
        pdf.setFont(stile, 12)
        # Allinea il testo all'inizio della pagina a sinistra
        pdf.drawString(x, y, riga)
        y -= 20  # Spostamento verticale per la riga successiva

        # Vai a capo se si raggiunge la fine della pagina
        if y < 20:
            pdf.showPage()  # Nuova pagina
            pdf.drawImage(lista_template[1], 0, 0, width, height)
            FrameFooter(pdf, stile)

    return y


def aggiungi_foto(pdf, stile, x, y, width, height, foto_path, cont, type=None, inq=""):
    foto_x = x
    foto_y = y
    if type == "mappa":
        foto_width = 530
        foto_height = 250
        foto_x = x + 5
        foto_y = y - 300

    else:
        foto_width = 545
        foto_height = 300
        foto_y = y - 340

    if foto_y < 30:
        # Passa a una nuova pagina
        pdf.showPage()
        pdf.drawImage(lista_template[1], 0, 0, width, height)
        FrameFooter(pdf, stile)
        y = 750  # Reset della posizione verticale
        foto_y = y - 300
        pdf.drawImage(foto_path, foto_x, foto_y,
                      width=foto_width, height=foto_height)
    elif foto_y == 30:
        pdf.drawImage(foto_path, foto_x, foto_y - 35,
                      width=foto_width, height=foto_height - 30)
    else:
        pdf.drawImage(foto_path, foto_x, foto_y,
                      width=foto_width, height=foto_height)

    # Aggiungi il tipo di foto
    if type != "mappa":
        add_title_foto(pdf, foto_x+5, foto_y + foto_height +
                       12, width, height, stile, inq=inq)

    # Controllo se l'immagine ridotta sfora il limite inferiore della pagina
    y = foto_y - 16
    return y


def merge_pdfs(npdf1, npdf2):
    merger = PdfMerger()

    # Apri i due file PDF
    with open(npdf1, "rb") as f1, open(npdf2, "rb") as f2:
        # Aggiungi i file PDF all'oggetto PdfMerger
        merger.append(PdfReader(npdf1))
        merger.append(PdfReader(npdf2))

    # Unisci i file PDF
    # Effettua l'eliminazione del file
    os.remove(npdf1)
    os.remove(npdf2)

    merger.write(f"{ABSOLUTE_PATH_REPORT}/{nome_report}.pdf")

    # Controlla se la cartella "immagini" esiste prima di eliminarla con tutto il suo contenuto
    if os.path.exists(ABSOLUTE_PATH_IMG):
        for item in os.listdir(ABSOLUTE_PATH_IMG):
            os.remove(os.path.join(ABSOLUTE_PATH_IMG, item))


def genera_Pagina_Iniziale(font_globale="Helvetica", stile_globale="", fontn=40, proj={}, freq=""):

    npdf1 = f"{ABSOLUTE_PATH_REPORT}/Pagina_{proj['alias_progetto']}_Prima.pdf"
    pdf = canvas.Canvas(npdf1)
    pdf.drawImage(lista_template[0], 0, 0, width=A4[0], height=A4[1])

    FrameHeaderAndBody(pdf, font_globale+stile_globale, fontn, proj, freq)
    FrameFooter(pdf, font_globale+stile_globale)
    pdf.save()
    return npdf1


def check_old_report(id: str, f: str, datastart: datetime, datafinish: datetime):

    url = f"{server}:5002/elenco_report"

    payload = {"apikey": "WDBNX4IUF66C", "id_progetto": id, "frequenze": f"[\"{f}\"]", "inizio": datastart.strftime(
        "%Y-%m-%d"), "fine": datafinish.strftime("%Y-%m-%d"), "rapido": "False"}

    req = requests.post(url, payload)

    try:
        report_disponibili = req.json()["result"]

        report_da_fare = []
        if f == "giornalieri" or f == "custom":
            presente = False
            for dat in range((datafinish - datastart).days):
                data = (datastart + timedelta(days=dat)
                        ).replace(day=(datastart + timedelta(days=dat)).day)

                # convertire data in una stringa che ha il seguente formato: Tue, 27 Feb 2024
                data = data.strftime("%a, %d %b %Y")

                presente = False
                for report in report_disponibili:
                    if report["periodo"]["start_date"].startswith(data):
                        presente = True
                        break
                if presente == False:
                    dat += 1
                    report_da_fare.append((datastart + timedelta(days=dat)))

    except:
        report_da_fare = [datastart]
        print(req.text)
    return report_da_fare


def composizione_report(nome_report: str):
    lista_file = os.listdir(ABSOLUTE_PATH_REPORT)

    # creare un pdf che segua il seguente ordine: file che temina con _Prima.pdf, file che termina con _Mappe.pdf, file che termina con _Analisi.pdf, file che termina con _Chart.pdf
    pdf_writer = PdfWriter()

    for fil in lista_file:
        if fil.endswith("_Prima.pdf"):
            pdf = PdfReader(f"{ABSOLUTE_PATH_REPORT}/{fil}")
            for page in pdf.pages:
                pdf_writer.add_page(page)

    for fil in lista_file:
        if fil.endswith("_Mappe.pdf"):
            pdf = PdfReader(f"{ABSOLUTE_PATH_REPORT}/{fil}")
            for page in pdf.pages:
                pdf_writer.add_page(page)

    for fil in lista_file:
        if fil.endswith("_Tabella_Analisi.pdf"):
            pdf = PdfReader(f"{ABSOLUTE_PATH_REPORT}/{fil}")
            for page in pdf.pages:
                pdf_writer.add_page(page)

    for fil in lista_file:
        if fil.endswith("_Analisi.pdf") and not fil.endswith("_Tabella_Analisi.pdf"):
            pdf = PdfReader(f"{ABSOLUTE_PATH_REPORT}/{fil}")
            for page in pdf.pages:
                pdf_writer.add_page(page)

    for fil in lista_file:
        if fil.endswith("_Chart.pdf"):
            pdf = PdfReader(f"{ABSOLUTE_PATH_REPORT}/{fil}")
            for page in pdf.pages:
                pdf_writer.add_page(page)

    with open(f"{ABSOLUTE_PATH_REPORT_FINALI}/{nome_report}.pdf", "wb") as out:
        pdf_writer.write(out)

    # cancellare tutti i file pdf che non sono il report finale

    for page in lista_file:
        if not page.endswith(f"{nome_report}.pdf"):
            os.remove(f"{ABSOLUTE_PATH_REPORT}/{page}")


TOKEN_WRITE = "1FPCPQCZPV7G"
progetti = retrieve_project("WDBNX4IUF66C")

for prog in progetti:
    clean_img()
    if prog["attivo"] is True:
        print(prog["alias_progetto"] + " " + str(prog["frequenze"]))

        if "lingua" in prog:
            LINGUA = prog["lingua"]

        if type(prog["frequenze"][0]) == int:
            frequenze = conversione_frequenza(prog["frequenze"])
        else:
            frequenze = prog["frequenze"]

        for f in frequenze:
            if f == "settimanali" and datetime.now().weekday() != 0:
                continue
            if f == "mensili" and datetime.now().day != 1:
                continue
            if f == "annuali" and datetime.now().day != 1 and datetime.now().month != 1:
                continue
            print(f)
            report_mancanti = check_old_report(
                prog["id_progetto"], f, datetime.now() - timedelta(days=20), datetime.now())

            print(report_mancanti)

            for data in report_mancanti:
                try:
                    prog["datastart"] = data

                    datastart, datafinish = get_start_end_date(f, prog)
                    nome_report = f"{prog['alias_progetto']}_{translation_data(LINGUA, datastart)}"

                    if f == "annuali":
                        nome_report = f"{prog['alias_progetto']}_{datastart.strftime('%Y')}"

                    # fare il confronto per vedere se è settimanale e in tal caso farlo solo se è di lunedi
                    if f == "settimanali":
                        nome_report = f"{prog['alias_progetto']}_{translation_data(LINGUA, datastart)}_{translation_data(LINGUA, datafinish)}"

                    if f == "mensili":
                        # creare il nome del report di questo tipo: alias_progetto_nomemese_anno
                        nome_mese = translation(
                            LINGUA, datastart.strftime('%B'))
                        nome_report = f"{prog['alias_progetto']}_{nome_mese}_{datastart.strftime('%Y')}"

                    if f == "custom":
                        nome_report = f"{prog['alias_progetto']}_{translation_data(LINGUA, datastart, True)}_{translation_data(LINGUA, datafinish, True)}"

                    pdf1 = genera_Pagina_Iniziale(proj=prog, freq=f)

                    conteggio_sforamenti(places=prog["luoghi"], datainizio=datastart, progetto=prog,
                                         datafine=datafinish, zoo=prog["zoom"], freq=f, pro=prog["pro"])

                    genera_Pagina_mappe(proj=prog, freq=f)

                    genera_Pagina_chart(proj=prog, freq=f)

                    delete = False

                    alias = prog["alias_progetto"]

                    if "CANNONE" in prog["alias_progetto"]:
                        alias = prog["alias_progetto"].replace(
                            "CANNONE SRL ", "")

                    payload = {"alias_progetto": alias, "metadata": json.dumps({"id_progetto": prog["id_progetto"], "frequenza": f, "nome_report": nome_report, "periodo": {
                        "start_date": datastart.strftime("%Y-%m-%d %H:%M"), "end_date": datafinish.strftime("%Y-%m-%d %H:%M")}}), "token": TOKEN_WRITE}

                    print(nome_report)

                    composizione_report(nome_report)

                    with open(f"{ABSOLUTE_PATH_REPORT_FINALI}/{nome_report}.pdf", "rb") as fw:
                        r = requests.post(
                            "http://192.168.1.150:5004/inserisci_report", files={"report": fw}, data=payload)
                        print(r.text)
                        if r.text == "Inserito":
                            delete = True

                    if delete:
                        os.remove(f"{ABSOLUTE_PATH_REPORT_FINALI}/{nome_report}.pdf")
                except:
                    print(
                        f'{prog["alias_progetto"]} {data.strftime("%d/%m/%Y")} - ERRORE {format_exc()}')
                    
time.sleep(2000000)
