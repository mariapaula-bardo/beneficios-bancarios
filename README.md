# beneficios-bancarios

Scraper + sitio estático que junta los descuentos/beneficios de Banco de Chile y
Banco Santander, los ordena por banco > categoría > día, y se publica solo como
una página web que después agregás a la pantalla de inicio de tu celular (queda
con ícono, sin barra de navegador, como una app).

Mismo patrón que usás en `paid-media-agent`: script en Python corre en
GitHub Actions con un cron, escribe un JSON + HTML, y GitHub Pages lo publica.
Acá el único cambio real es que las páginas de beneficios de ambos bancos son
SPA (React/Vue) que cargan el contenido con JavaScript después de renderizar,
así que **no sirve `requests` + BeautifulSoup**: hay que usar Playwright
(navegador headless) para que el JS corra y después leer el HTML resultante.

## Estructura

```
scraper/
  scrape_bancochile.py   -> abre la página con Playwright, extrae beneficios
  scrape_santander.py    -> ídem para Santander
  build_site.py          -> junta ambos JSON, genera docs/index.html + manifest
  run.py                 -> orquesta: scrapea los 2 bancos, guarda data/beneficios.json, build_site
docs/                     -> output publicado por GitHub Pages (se regenera solo)
.github/workflows/scrape.yml -> cron diario que corre todo y hace commit del docs/
```

## Lo que falta hacer (esto es un esqueleto, no un scraper terminado)

Los selectores CSS en `scrape_bancochile.py` y `scrape_santander.py` son
placeholders (`.beneficio-card`, `.beneficio-titulo`, etc.) — necesitás
inspeccionar el HTML real que se renderiza para reemplazarlos por los
correctos. Para eso:

1. Abrí Claude Code (terminal, VS Code o la app de escritorio) en esta carpeta.
2. Pedile que use **Claude in Chrome** (o que corra Playwright con
   `headless=False` localmente) para navegar a:
   - `https://sitiospublicos.bancochile.cl/personas/beneficios`
   - `https://banco.santander.cl/beneficios/`
   y que inspeccione el DOM ya renderizado para sacar los selectores reales
   de cada tarjeta de beneficio (comercio, categoría, día, % descuento,
   canal — online/tienda física —, vigencia).
3. Reemplaza los placeholders y corré `python scraper/run.py` localmente para
   validar que el JSON sale bien poblado.
4. Subí el repo a tu GitHub personal (no al de Maxxa) y activá GitHub Pages
   apuntando a la carpeta `docs/` (rama main).
5. Activá el workflow de Actions (ya viene con cron diario a las 08:00
   Chile, ajustable).

## Cómo queda "como app" en el celular

`build_site.py` genera un `manifest.json` y agrega los meta tags necesarios
para iOS y Android. Una vez publicado en GitHub Pages:

- **Android/Chrome:** abrís la URL, menú (⋮) → "Agregar a pantalla de inicio".
- **iPhone/Safari:** abrís la URL, botón compartir → "Agregar a pantalla de
  inicio".

En ambos casos queda un ícono en tu pantalla que abre sin barra de
navegador (modo `standalone`), como una app nativa — aunque técnicamente es
una PWA liviana.

## Aviso

Solo se scrapea información pública de las páginas de beneficios (sin login).
Si algún descuento específico solo aparece iniciando sesión en la banca en
línea, eso queda afuera — nunca se deben poner credenciales bancarias en un
scraper automatizado.
