import time
from widget_picture_generator import widget_picture_generator

 # Init the generator (the constructor accept width and height)
wpg = widget_picture_generator("WDBNX4IUF66C")

# Generate an example picture
wpg.get_widget_picture_file("test.png", "widget_data_chart", {
    "device": {
        "key": 'ITCAMBAT134567',
        "value": 'ITCAMBAT134567'
    },
    "period": 'settimana',
    "type": [ 'aqi' ],
    "chart_type": 'bar',
    "minutes": 10,
    "showTitle": True,
    "showGrid": True,
    "showDots": True,
    "showSmoothLine": True,
    "showLegend": True,
    "_defaultStateKey": [ 'device', 'key' ]
})

# Destroy the driver
wpg.destroy()
time.sleep(200000)