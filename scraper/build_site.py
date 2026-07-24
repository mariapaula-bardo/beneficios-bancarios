"""Genera docs/index.html + manifest.json a partir del JSON de beneficios.

Diseño mobile-first porque el uso real va a ser desde el celular, agregado
a la pantalla de inicio. Incluye filtros simples por banco, categoría y día
hechos con JS plano (sin frameworks, para no depender de un build step).

Se llama "docs/" (no "site/") porque GitHub Pages, en el modo "Deploy from
a branch", solo deja elegir la raíz del repo o una carpeta llamada
"docs" como origen — no admite un nombre de carpeta arbitrario.
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
SITE_DIR = ROOT / "docs"

MANIFEST = {
    "name": "Beneficios Bancarios",
    "short_name": "Beneficios",
    "start_url": "./index.html",
    "display": "standalone",
    "background_color": "#101314",
    "theme_color": "#101314",
    "icons": [
        {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
    ],
}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es-CL">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Beneficios Bancarios</title>

<link rel="manifest" href="manifest.json">
<meta name="theme-color" content="#101314">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Beneficios">
<meta name="build-timestamp" content="{actualizado}">
<link rel="apple-touch-icon" href="icon-192.png">

<style>
  :root {{
    --bg: #101314;
    --card-bg: #1b1f21;
    --text: #f2f2f0;
    --muted: #9aa0a3;
    --chile: #d92b2b;
    --santander: #ec0000;
    --accent: #3ddc97;
    --radius: 14px;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding-bottom: calc(40px + env(safe-area-inset-bottom));
  }}
  header {{
    /* En modo "app" (agregado a la pantalla de inicio) el contenido puede
       quedar debajo del notch/Dynamic Island; env(safe-area-inset-top)
       empuja el header para que no quede tapado. */
    padding: calc(20px + env(safe-area-inset-top)) 16px 12px;
    position: sticky;
    top: 0;
    background: var(--bg);
    z-index: 10;
    border-bottom: 1px solid #262b2d;
  }}
  header h1 {{ margin: 0 0 2px; font-size: 20px; }}
  header p {{ margin: 0; font-size: 12px; color: var(--muted); }}

  .buscador {{
    padding: 12px 16px 0;
  }}
  .buscador input {{
    width: 100%;
    background: var(--card-bg);
    color: var(--text);
    border: 1px solid #2c3234;
    border-radius: 10px;
    padding: 10px 12px;
    font-size: 14px;
  }}
  .buscador input::placeholder {{ color: var(--muted); }}

  .filters {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 12px 16px;
  }}
  .filters select {{
    background: var(--card-bg);
    color: var(--text);
    border: 1px solid #2c3234;
    border-radius: 10px;
    padding: 8px 10px;
    font-size: 13px;
    flex: 1 1 auto;
    min-width: 0;
  }}

  main {{ padding: 0 16px; }}
  .grupo-banco {{ margin-top: 18px; }}
  .grupo-banco h2 {{
    font-size: 15px;
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0 0 10px;
  }}
  .dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
  .dot.chile {{ background: var(--chile); }}
  .dot.santander {{ background: var(--santander); }}

  .card {{
    background: var(--card-bg);
    border-radius: var(--radius);
    margin-bottom: 10px;
    overflow: hidden;
  }}
  .card-summary {{
    padding: 14px;
    cursor: pointer;
    list-style: none;
  }}
  .card-summary::-webkit-details-marker {{ display: none; }}
  .card-summary::after {{
    content: '▾';
    float: right;
    color: var(--muted);
    margin-left: 8px;
  }}
  details.card[open] > .card-summary::after {{ content: '▴'; }}
  .card-top {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 8px;
  }}
  .card-top .comercio {{ font-size: 15px; font-weight: 600; }}
  .card-top .descuento {{
    font-size: 13px;
    font-weight: 700;
    color: var(--accent);
    white-space: nowrap;
  }}
  .card-meta {{
    margin-top: 6px;
    font-size: 12px;
    color: var(--muted);
    display: flex;
    flex-wrap: wrap;
    gap: 6px 12px;
  }}
  .tag {{
    background: #262b2d;
    border-radius: 6px;
    padding: 2px 7px;
  }}

  .card-detail {{
    padding: 0 14px 14px;
  }}
  .detalle-bloque {{
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid #262b2d;
  }}
  .detalle-bloque h4 {{
    margin: 0 0 6px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: .04em;
    color: var(--muted);
  }}
  .detalle-lista {{
    margin: 0;
    padding-left: 18px;
    font-size: 13px;
    line-height: 1.5;
  }}
  .detalle-lista li {{ margin-bottom: 4px; }}
  .detalle-lista li.muted {{ color: var(--muted); list-style: none; margin-left: -18px; }}
  .buscador-sucursales {{
    width: 100%;
    box-sizing: border-box;
    margin-bottom: 8px;
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid #2c3234;
    background: var(--bg);
    color: var(--text);
    font-size: 13px;
  }}

  .vacio {{
    text-align: center;
    color: var(--muted);
    padding: 40px 20px;
    font-size: 13px;
  }}
</style>
</head>
<body>

<header>
  <h1>Beneficios Bancarios</h1>
  <p>Actualizado: {actualizado} · {total} beneficios</p>
</header>

<div class="buscador">
  <input type="text" id="f-buscar" placeholder="Buscar por comercio o comuna..." autocomplete="off">
</div>

<div class="filters">
  <select id="f-banco">
    <option value="">Todos los bancos</option>
  </select>
  <select id="f-categoria">
    <option value="">Todas las categorías</option>
    <option value="__sin_categoria__">Sin categoría</option>
  </select>
  <select id="f-dia">
    <option value="">Todos los días</option>
  </select>
</div>

<main id="main"></main>

<script>
const DATA = {data_json};

const mainEl = document.getElementById('main');
const fBuscar = document.getElementById('f-buscar');
const fBanco = document.getElementById('f-banco');
const fCategoria = document.getElementById('f-categoria');
const fDia = document.getElementById('f-dia');

const ORDEN_DIAS = ["Todos los días", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
const SIN_CATEGORIA = "__sin_categoria__";

function unique(arr) {{
  return [...new Set(arr.filter(Boolean))].sort();
}}

function uniqueDias(arrOfArrays) {{
  const presentes = new Set(arrOfArrays.flat().filter(Boolean));
  return ORDEN_DIAS.filter(d => presentes.has(d));
}}

function normalizarTexto(str) {{
  // saca tildes (ej. "Ñuñoa") normalizando a forma descompuesta y
  // quitando las marcas diacríticas, así se puede buscar sin acentos
  return (str || '')
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}}

function coincideBusqueda(b, termino) {{
  if (!termino) return true;
  const campos = [b.comercio, ...(b.sucursales || [])].join(' ');
  return normalizarTexto(campos).includes(termino);
}}

function fillSelect(select, values) {{
  values.forEach(v => {{
    const opt = document.createElement('option');
    opt.value = v;
    opt.textContent = v;
    select.appendChild(opt);
  }});
}}

function escapeHtml(str) {{
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}}

const SUCURSALES_BUSCADOR_MIN = 15;

function renderCondiciones(lista) {{
  if (!lista || !lista.length) return '';
  const items = lista.map(c => `<li>${{escapeHtml(c)}}</li>`).join('');
  return `<div class="detalle-bloque"><h4>Condiciones</h4><ul class="detalle-lista">${{items}}</ul></div>`;
}}

function renderSucursalesBloque(contenedor, sucursales) {{
  if (!sucursales || !sucursales.length) return;

  const bloque = document.createElement('div');
  bloque.className = 'detalle-bloque';

  const titulo = document.createElement('h4');
  titulo.textContent = `Sucursales (${{sucursales.length}})`;
  bloque.appendChild(titulo);

  const lista = document.createElement('ul');
  lista.className = 'detalle-lista';

  function pintar(filtro) {{
    lista.innerHTML = '';
    const filtro_lower = filtro.trim().toLowerCase();
    const filtradas = filtro_lower
      ? sucursales.filter(s => s.toLowerCase().includes(filtro_lower))
      : sucursales;
    if (filtradas.length === 0) {{
      const li = document.createElement('li');
      li.className = 'muted';
      li.textContent = 'Sin resultados.';
      lista.appendChild(li);
      return;
    }}
    filtradas.forEach(s => {{
      const li = document.createElement('li');
      li.textContent = s;
      lista.appendChild(li);
    }});
  }}

  if (sucursales.length >= SUCURSALES_BUSCADOR_MIN) {{
    const buscador = document.createElement('input');
    buscador.type = 'text';
    buscador.placeholder = 'Buscar por comuna o dirección...';
    buscador.className = 'buscador-sucursales';
    buscador.addEventListener('click', e => e.stopPropagation());
    buscador.addEventListener('input', () => pintar(buscador.value));
    bloque.appendChild(buscador);
  }}

  bloque.appendChild(lista);
  pintar('');
  contenedor.appendChild(bloque);
}}

fillSelect(fBanco, unique(DATA.map(b => b.banco)));
fillSelect(fCategoria, unique(DATA.map(b => b.categoria)));
fillSelect(fDia, uniqueDias(DATA.map(b => b.dia)));

function render() {{
  const banco = fBanco.value;
  const categoria = fCategoria.value;
  const dia = fDia.value;
  const busqueda = normalizarTexto(fBuscar.value.trim());

  const filtrados = DATA.filter(b =>
    (!banco || b.banco === banco) &&
    (!categoria || (categoria === SIN_CATEGORIA ? !b.categoria : b.categoria === categoria)) &&
    (!dia || (Array.isArray(b.dia) && b.dia.includes(dia))) &&
    coincideBusqueda(b, busqueda)
  );

  mainEl.innerHTML = '';

  if (filtrados.length === 0) {{
    mainEl.innerHTML = '<div class="vacio">No hay beneficios con esos filtros.</div>';
    return;
  }}

  const porBanco = {{}};
  filtrados.forEach(b => {{
    porBanco[b.banco] = porBanco[b.banco] || [];
    porBanco[b.banco].push(b);
  }});

  Object.keys(porBanco).sort().forEach(banco => {{
    const grupo = document.createElement('div');
    grupo.className = 'grupo-banco';

    const dotClass = banco.toLowerCase().includes('santander') ? 'santander' : 'chile';
    grupo.innerHTML = `<h2><span class="dot ${{dotClass}}"></span>${{banco}}</h2>`;

    porBanco[banco].forEach(b => {{
      const tieneDetalle = (b.condiciones && b.condiciones.length) || (b.sucursales && b.sucursales.length);

      const card = document.createElement(tieneDetalle ? 'details' : 'div');
      card.className = 'card';

      const header = document.createElement(tieneDetalle ? 'summary' : 'div');
      header.className = 'card-summary';
      header.innerHTML = `
        <div class="card-top">
          <div class="comercio">${{escapeHtml(b.comercio || 'Sin nombre')}}</div>
          <div class="descuento">${{escapeHtml(b.descuento || '')}}</div>
        </div>
        <div class="card-meta">
          ${{b.categoria ? `<span class="tag">${{escapeHtml(b.categoria)}}</span>` : ''}}
          ${{b.dia_texto ? `<span class="tag">${{escapeHtml(b.dia_texto)}}</span>` : ''}}
          ${{b.canal ? `<span class="tag">${{escapeHtml(b.canal)}}</span>` : ''}}
          ${{b.vigencia ? `<span class="tag">${{escapeHtml(b.vigencia)}}</span>` : ''}}
        </div>
      `;
      card.appendChild(header);

      if (tieneDetalle) {{
        const detalle = document.createElement('div');
        detalle.className = 'card-detail';
        let renderizado = false;
        card.addEventListener('toggle', () => {{
          if (card.open && !renderizado) {{
            renderizado = true;
            detalle.innerHTML = renderCondiciones(b.condiciones);
            renderSucursalesBloque(detalle, b.sucursales);
          }}
        }});
        card.appendChild(detalle);
      }}

      grupo.appendChild(card);
    }});

    mainEl.appendChild(grupo);
  }});
}}

[fBanco, fCategoria, fDia].forEach(el => el.addEventListener('change', render));
fBuscar.addEventListener('input', render);
render();

// Las apps agregadas a la pantalla de inicio en iOS a veces reabren la
// versión que ya tenían cargada en vez de pedirle una nueva al servidor.
// Acá se chequea en segundo plano si salió una versión más nueva
// (comparando el build-timestamp embebido) y, si la hay, se recarga sola
// una vez — así no hace falta borrar y volver a agregar el acceso directo.
(function comprobarActualizacion() {{
  var metaActual = document.querySelector('meta[name="build-timestamp"]');
  var buildActual = metaActual && metaActual.content;
  if (!buildActual) return;

  fetch(location.href, {{cache: 'no-store'}})
    .then(function(res) {{ return res.text(); }})
    .then(function(html) {{
      var fresco = new DOMParser().parseFromString(html, 'text/html');
      var metaFresco = fresco.querySelector('meta[name="build-timestamp"]');
      var buildFresco = metaFresco && metaFresco.content;
      if (!buildFresco || buildFresco === buildActual) return;
      if (sessionStorage.getItem('build-visto') === buildFresco) return;
      sessionStorage.setItem('build-visto', buildFresco);
      location.reload();
    }})
    .catch(function() {{}});
}})();
</script>

</body>
</html>
"""


def build(output: dict):
    SITE_DIR.mkdir(exist_ok=True)

    html = HTML_TEMPLATE.format(
        actualizado=output["actualizado"],
        total=len(output["beneficios"]),
        data_json=json.dumps(output["beneficios"], ensure_ascii=False),
    )

    (SITE_DIR / "index.html").write_text(html, encoding="utf-8")
    (SITE_DIR / "manifest.json").write_text(
        json.dumps(MANIFEST, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Nota: falta generar/copiar icon-192.png y icon-512.png a site/ para que
    # el ícono de la pantalla de inicio no sea el genérico del navegador.


if __name__ == "__main__":
    import json as _json
    sample = _json.loads((ROOT / "data" / "beneficios.json").read_text(encoding="utf-8"))
    build(sample)
