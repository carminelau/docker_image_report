import time
from widget_picture_generator import widget_picture_generator

for i in range(10):
    # Init the generator (the constructor accept width and height)
    wpg = widget_picture_generator("WDBNX4IUF66C")

    conf = {
        "dataType": 4,
        "sources": [
            {
                "type": "guide",
                "source": None,
                "parameter": "o3",
                "chartType": "line",
                "yAxis": "y",
                "selectedColor": "#e53935",
                "smoothLine": True,
                "showDots": True,
                "guideValue": 120,
                "name": "Limite O3",
                "id": "_s9rp7lpfn",
            },
            {
                "type": "device",
                "source": "ITYDPXJXGCBMN9",
                "parameter": "o3",
                "chartType": "line",
                "yAxis": "y",
                "selectedColor": "#ff9800",
                "smoothLine": True,
                "showDots": True,
                "name": "ITYDPXJXGCBMN9",
                "id": "ITYDPXJXGCBMN9",
            },
        ],
        "selectedGranularity": "hourly",
        "showGrid": False,
        "showLegend": True,
        "selectedRatio": 1.3333333333333333,
        "showChartFullscreen": True,
        "from": "2025-12-01T00:00:00",
        "to": "2025-12-01T23:59:59",
    }

    time.sleep(10)

    # Generate an example picture
    if i > 2:
        wpg.get_widget_picture_file(f"test{i}.png", "tool_analizza_dati", conf, timeout=i)
    else:
        wpg.get_widget_picture_file(f"test{i}.png", "tool_analizza_dati", conf)

    # Destroy the driver
    wpg.destroy()
    time.sleep(15)
time.sleep(200000)
