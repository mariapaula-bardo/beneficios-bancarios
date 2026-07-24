"""
Scraper de beneficios/descuentos de Banco Santander Chile.

La página muestra "Cargando el sitio, no recargues la página" mientras el
JS arma el contenido, así que hay que esperar a que Playwright termine de
renderizar antes de pedirle datos al sitio (ver scrape() más abajo).

Antes esto recorría la paginación de la grilla clickeando el botón
"siguiente" 14 veces y leyendo el DOM de cada tarjeta. Se cambió a pegarle
directo al endpoint JSON que la propia página llama para armar esa
grilla:

    /beneficios/promociones.json?per_page=9999&custom_fields=true

Sin filtro de "tags" devuelve los 288 beneficios completos en una sola
respuesta (se confirmó que `meta.total_entries` coincide con el total
real). Es más simple y más confiable que depender de que el botón
"siguiente" seguido siga funcionando igual, y de paso trae varios campos
que no estaban en la tarjeta:

- "Bajada externa" (o "Bajada interna" si la primera viene vacía): el
  mismo texto de descuento + día que se leía antes del DOM.
- "description": HTML con las condiciones específicas del beneficio (el
  mismo contenido que se ve en el modal "Más información" del sitio).
- "conditions": el disclaimer legal genérico (misma responsabilidad del
  comercio, garantía estatal de depósitos, etc.) que también se muestra
  en ese modal.
- "location_street"/lat/lng: dirección puntual, cuando el beneficio tiene
  una (en la práctica casi siempre viene vacío en este dataset).
- "tags": incluye tags "cat-*" (cat-sabores, cat-descuentos,
  cat-cuotas-sin-interes, cat-multiplica-millas, cat-verdes, cat-otros)
  que dan una categoría real — el sitio no la mostraba en la tarjeta, así
  que antes quedaba siempre en None.

"dia" sigue extrayéndose con la misma regex de normalize.py que usa
Banco de Chile (en vez de los tags de día, que también vienen) para que
ambos bancos usen exactamente la misma lógica de días.
"""

import re

from playwright.sync_api import sync_playwright

from normalize import (
    extraer_dias,
    normalizar_categoria,
    consolidar_categoria,
    rescatar_categoria_texto,
    aplicar_categoria_manual,
    completar_categoria_faltante,
    html_a_bullets,
)

URL = "https://banco.santander.cl/beneficios/"
API_PATH = "/beneficios/promociones.json"

SELECTOR_CARD = "div.discount"  # solo se usa para confirmar que la SPA ya cargó

_DESCUENTO_RE = re.compile(
    r"\d+%\s*(?:a\s*\d+%\s*)?(?:dcto\.?|descuento)", re.IGNORECASE
)


def _split_descuento_dia(raw):
    """"Bajada externa" mezcla el % de descuento con el texto del día."""
    if not raw:
        return None, None

    match = _DESCUENTO_RE.search(raw)
    descuento = match.group(0) if match else None
    dia = _DESCUENTO_RE.sub("", raw).strip(" .")
    return descuento, (dia or None)


def _categoria_desde_tags(tags):
    for tag in tags or []:
        if tag.startswith("cat-"):
            return normalizar_categoria(tag[len("cat-"):])
    return None


def _parse_promocion(promo):
    custom = promo.get("custom_fields") or {}
    bajada = (
        (custom.get("Bajada externa") or {}).get("value")
        or (custom.get("Bajada interna") or {}).get("value")
    )
    descuento, dia_texto = _split_descuento_dia(bajada)

    condiciones = html_a_bullets(promo.get("description"))
    disclaimer = (promo.get("conditions") or "").strip()
    if disclaimer:
        condiciones = condiciones + [re.sub(r"\s+", " ", disclaimer)]

    ubicacion = (promo.get("location_street") or "").strip()
    comercio = (promo.get("title") or "").strip() or None
    categoria = consolidar_categoria(_categoria_desde_tags(promo.get("tags")), comercio)
    categoria = rescatar_categoria_texto(categoria, comercio, promo.get("description"))
    categoria = aplicar_categoria_manual(categoria, comercio)
    categoria = completar_categoria_faltante(categoria, comercio, condiciones)

    return {
        "banco": "Banco Santander",
        "comercio": comercio,
        "categoria": categoria,
        "descuento": descuento,
        "dia": extraer_dias(bajada),
        "dia_texto": dia_texto,
        "canal": None,  # no viene en esta fuente
        "vigencia": None,  # ídem: no viene un campo de vigencia comparable al de Banco de Chile
        "condiciones": condiciones,
        "sucursales": [ubicacion] if ubicacion else [],
    }


def scrape():
    with sync_playwright() as p:
        # headless=True queda bloqueado por la protección anti-bot del sitio
        # (la página nunca hidrata); con headless=False carga normal.
        # wait_until="load" en vez de "networkidle" porque el sitio tiene
        # trackers que hacen que la red nunca quede en idle.
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(locale="es-CL")
        page.goto(URL, wait_until="load", timeout=60_000)

        # Confirma que la SPA ya renderizó (y que la validación anti-bot ya
        # se resolvió) antes de pedirle datos al endpoint JSON.
        page.wait_for_selector(SELECTOR_CARD, timeout=30_000)

        data = page.evaluate(
            """async (apiPath) => {
                const res = await fetch(`${apiPath}?per_page=9999&custom_fields=true`);
                return await res.json();
            }""",
            API_PATH,
        )

        promociones = data.get("promociones") or []
        beneficios = [_parse_promocion(p) for p in promociones]

        browser.close()

    return beneficios


if __name__ == "__main__":
    import json
    print(json.dumps(scrape(), ensure_ascii=False, indent=2))
