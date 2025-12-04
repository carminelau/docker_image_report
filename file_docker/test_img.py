import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, JavascriptException
import json
import time

SQUARE_EXPORT_URL = "https://square.sensesquare.eu"


class WidgetPictureGenerator:
    def __init__(self, apikey, width=1280, height=720, timeout=30):
        opts = webdriver.ChromeOptions()
        # Headless “nuovo” e flag utili in Docker
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--hide-scrollbars")
        opts.add_argument(f"--window-size={width},{height}")
        self._driver = webdriver.Chrome(options=opts)
        self._wait = WebDriverWait(self._driver, timeout)
        self._apikey = apikey
        self._width = width
        self._height = height

    def _inject_config(self, wid, state, theme):
        cfg = {"apikey": self._apikey, "id": wid, "state": state, "theme": theme}
        payload = json.dumps(cfg, separators=(",", ":"))
        # Inietta la config PRIMA di caricare la pagina
        self._driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": f"window._w_config = {payload};"},
        )

    def _wait_widget_ready(self):
        # Attendi che il root del widget sia presente e “rendered”
        # Sostituisci i selettori qui sotto con quelli reali del tuo widget
        ROOT_SEL = "[data-testid='widget-root']"  # es. un div root del widget
        CANVAS_SEL = "canvas"  # se il widget disegna su canvas

        self._wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ROOT_SEL)))
        root = self._driver.find_element(By.CSS_SELECTOR, ROOT_SEL)

        # Attendi che il root sia visibile e con dimensioni > 0
        self._wait.until(
            lambda d: root.is_displayed()
            and root.size["height"] > 0
            and root.size["width"] > 0
        )

        # Se usa canvas, aspetta che il canvas esista e non sia “bianco” (grezza euristica)
        canvases = self._driver.find_elements(
            By.CSS_SELECTOR, f"{ROOT_SEL} {CANVAS_SEL}"
        )
        if canvases:
            canvas = canvases[0]
            # Aspetta 2 frame di rendering
            try:
                self._driver.execute_script(
                    """
                    return new Promise(resolve => {
                      requestAnimationFrame(() => requestAnimationFrame(resolve));
                    });
                """
                )
            except JavascriptException:
                pass

            # Poll su dataURL length per evitare bianco (threshold empirico)
            def canvas_has_pixels(d):
                try:
                    return d.execute_script(
                        """
                        const c = arguments[0];
                        if (!c) return false;
                        const ctx = c.getContext('2d');
                        if (!ctx) return false;
                        const bbox = c.getBoundingClientRect();
                        if (bbox.width < 2 || bbox.height < 2) return false;
                        const durl = c.toDataURL('image/png');
                        return durl && durl.length > 10000; // ~10KB
                    """,
                        canvas,
                    )
                except Exception:
                    return False

            end = time.time() + 10
            while time.time() < end:
                if canvas_has_pixels(self._driver):
                    break
                time.sleep(0.2)

    def _load_widget(self, wid, state, theme="light", post_load_sleep=0.5):
        # Importante: set window size prima
        self._driver.set_window_size(self._width, self._height)
        self._inject_config(wid, state, theme)
        self._driver.get(SQUARE_EXPORT_URL)

        # Se hai un loader, aspetta che sparisca (usa locator corretto)
        try:
            self._wait.until(
                EC.invisibility_of_element_located(
                    (By.CSS_SELECTOR, ".generic-container")
                )
            )
        except TimeoutException:
            pass  # non bloccare se il selettore non è affidabile

        self._wait_widget_ready()
        time.sleep(post_load_sleep)  # piccolo margine per font/grafici

    def get_widget_png_bytes(self, wid, state, theme="light"):
        self._load_widget(wid, state, theme)
        return self._driver.get_screenshot_as_png()

    def save_widget_png(self, filename, wid, state, theme="light"):
        self._load_widget(wid, state, theme)
        # Migliore: screenshot del root invece dell’intera pagina
        try:
            root = self._driver.find_element(
                By.CSS_SELECTOR, "[data-testid='widget-root']"
            )
            root.screenshot(filename)
            return True
        except Exception:
            return self._driver.save_screenshot(filename)

    def destroy(self):
        try:
            self._driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    for i in range(10):
        wpg = WidgetPictureGenerator("WDBNX4IUF66C")

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

        ok = wpg.save_widget_png("test.png", "tool_analizza_dati", conf, theme="light")
        wpg.destroy()

time.sleep(200000)
