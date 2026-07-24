"""
Scraper de beneficios/descuentos de Banco de Chile.

La página es una SPA: el HTML inicial viene casi vacío y el contenido se
inyecta con JS. Por eso usamos Playwright (Chromium headless) en vez de
requests/BeautifulSoup.

La grilla de tarjetas ("Todos los beneficios", 811 en total) está
virtualizada: el DOM solo llega a mostrar un primer bloque y ni el scroll
por rueda del mouse ni `window.scrollTo` la hacen avanzar (se probó a mano
con Playwright headless=False y con el navegador de Claude in Chrome — el
scroll queda colgado). Inspeccionando las peticiones de red de esa misma
página se ve que el propio sitio arma la grilla pidiendo datos a una API
JSON interna, paginada de a 100:

    /api/content/spaces/personas/types/beneficios/entries?page=N&per_page=100

Esa API es la fuente real de los 811 beneficios (el `meta.total_entries`
que devuelve coincide exactamente con el "811 beneficios disponibles" que
muestra la página), así que en vez de forzar un scroll que no responde,
la paginación se implementa pidiendo esas páginas directamente. Se hace
con `page.evaluate` (fetch dentro del contexto de la página) para
reutilizar la sesión/cookies que Incapsula (la protección anti-bot del
sitio) ya validó al cargar la página con headless=False — por eso primero
se navega a la URL y se espera a que aparezca al menos una tarjeta real,
igual que antes.

Cada entry trae campos propios para comercio, categoría, descuento, día +
canal (mezclados en el mismo texto, así que se separan con regex) y
vigencia — bastante más completo que lo que se ve en la tarjeta del
listado.

"dia" queda como una lista de días canónicos (lunes a domingo, o "Todos
los días") extraídos por regex del texto libre, para que sirva como
filtro; el texto original completo se guarda aparte en "dia_texto" para no
perder detalle al mostrar la tarjeta. "categoria" se normaliza a Title
Case y descarta los slugs de promoción que no son una categoría real
(ver normalize.py).

"condiciones" sale del campo "Descripcion" (HTML con las condiciones del
beneficio, normalmente una lista <ul><li>) convertido a una lista de
strings de texto plano. "sucursales" sale de "Sucursales" (otra lista
HTML, formato libre tipo "nombre;dirección;región;comuna;..." que no
siempre respeta el mismo orden/cantidad de campos) limpiada a una lista
de direcciones en texto plano.
"""

import re

from playwright.sync_api import sync_playwright

from normalize import (
    extraer_dias,
    normalizar_categoria,
    consolidar_categoria,
    aplicar_categoria_manual,
    completar_categoria_faltante,
    html_a_bullets,
    parse_sucursales_bancochile,
)

URL = "https://sitiospublicos.bancochile.cl/personas/beneficios/todos-los-beneficios"
API_URL = "/api/content/spaces/personas/types/beneficios/entries"
API_PER_PAGE = 100

SELECTOR_CARD = "a.card"  # solo se usa para confirmar que la SPA ya cargó

_CANAL_STRIP_RE = re.compile(r"\s*(?:y\s+)?(?:presencial(?:es)?|online)\.?", re.IGNORECASE)
_PRESENCIAL_RE = re.compile(r"presencial(?:es)?", re.IGNORECASE)
_ONLINE_RE = re.compile(r"online", re.IGNORECASE)
_DESCUENTO_SEP_RE = re.compile(r"\s*;\s*")


def _split_dia_canal(raw):
    """El campo "Extracto" de la API mezcla día y canal en un solo texto."""
    if not raw:
        return None, None

    tiene_presencial = bool(_PRESENCIAL_RE.search(raw))
    tiene_online = bool(_ONLINE_RE.search(raw))
    if tiene_presencial and tiene_online:
        canal = "Ambos"
    elif tiene_online:
        canal = "Online"
    elif tiene_presencial:
        canal = "Tienda física"
    else:
        canal = None

    dia = _CANAL_STRIP_RE.sub("", raw).strip(" .")
    return (dia or None), canal


def _clean_descuento(raw):
    # La API entrega el descuento como "20%; dto." — se normaliza a "20% dto."
    if not raw:
        return None
    return _DESCUENTO_SEP_RE.sub(" ", raw).strip() or None


def _parse_entry(entry):
    fields = entry.get("fields", {})
    meta = entry.get("meta", {})

    extracto = fields.get("Extracto")
    dia_texto, canal = _split_dia_canal(extracto)
    comercio = (fields.get("Titulo") or "").strip() or None
    condiciones = html_a_bullets(fields.get("Descripcion"))

    categoria = consolidar_categoria(normalizar_categoria(meta.get("category_name")), comercio)
    categoria = aplicar_categoria_manual(categoria, comercio)
    categoria = completar_categoria_faltante(categoria, comercio, condiciones)

    return {
        "banco": "Banco de Chile",
        "comercio": comercio,
        "categoria": categoria,
        "descuento": _clean_descuento(fields.get("Tipo Beneficio")),
        "dia": extraer_dias(extracto),
        "dia_texto": dia_texto,
        "canal": canal,
        "vigencia": (fields.get("Vigencia") or "").strip() or None,
        "condiciones": condiciones,
        "sucursales": parse_sucursales_bancochile(fields.get("Sucursales")),
    }


def scrape():
    beneficios = []

    with sync_playwright() as p:
        # headless=True queda bloqueado por la protección anti-bot del sitio
        # (la página nunca hidrata y `a.card` no aparece); con headless=False
        # carga normal. wait_until="load" en vez de "networkidle" porque el
        # sitio tiene trackers que hacen que la red nunca quede en idle.
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(locale="es-CL")
        page.goto(URL, wait_until="load", timeout=60_000)

        # Confirma que la SPA ya renderizó (y que la validación anti-bot de
        # Incapsula ya se resolvió) antes de pedirle datos a la API interna.
        page.wait_for_selector(SELECTOR_CARD, timeout=30_000)

        page_num = 1
        total_pages = None
        while total_pages is None or page_num <= total_pages:
            data = page.evaluate(
                """async ({apiUrl, page, perPage}) => {
                    const res = await fetch(`${apiUrl}?page=${page}&per_page=${perPage}`);
                    return await res.json();
                }""",
                {"apiUrl": API_URL, "page": page_num, "perPage": API_PER_PAGE},
            )

            entries = data.get("entries") or []
            if not entries:
                break

            for entry in entries:
                beneficios.append(_parse_entry(entry))

            if total_pages is None:
                total_pages = data.get("meta", {}).get("total_pages")
                if not total_pages:
                    break  # no se pudo leer la paginación, no seguir adivinando

            page_num += 1

        browser.close()

    return beneficios


if __name__ == "__main__":
    import json
    print(json.dumps(scrape(), ensure_ascii=False, indent=2))
