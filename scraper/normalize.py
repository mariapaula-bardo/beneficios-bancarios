"""
Normalización compartida entre los dos scrapers.

extraer_dias(texto): saca un set canónico de días (lunes a domingo, o
"Todos los días") desde texto libre, ignorando todo lo que no sea un día
real (cuotas, precios, textos promocionales). Si el texto menciona varios
días (o un rango tipo "lunes a viernes") devuelve todos los que
correspondan.

normalizar_categoria(raw): pasa el nombre de categoría a un Title Case
consistente y descarta los que en realidad son slugs/nombres de promoción
sin sentido como categoría real (ej. "40-de-descuento-visa",
"dolares-premio").

consolidar_categoria(categoria, comercio): junta las ~23 categorías
crudas de ambos bancos (ya pasadas por normalizar_categoria) en un set
más chico de 8. Los catch-all genéricos ("Beneficios y Descuentos",
"Descuentos", "Otros", "Catálogo Productos", "Multiplica Millas" — el
bucket "Retail y Otras Marcas") se revisan además por nombre de comercio
para rescatar los que en realidad son de Viajes o de Entretención y
Deportes (rent a car, hoteles, centros de ski, etc. que el banco no
categorizó como tal).

html_a_bullets(html): convierte un bloque HTML (típicamente <ul><li>...)
en una lista de strings de texto plano, uno por punto, para usar como
"condiciones".

parse_sucursales_bancochile(html): el campo "Sucursales" de la API de
Banco de Chile es una lista en HTML con formato libre separado por ";"
(no siempre el mismo orden ni la misma cantidad de campos), así que en
vez de asumir posiciones fijas se limpia cada ítem a una sola línea de
texto buscable.
"""

import html as _html_module
import re

CANONICAL_DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
TODOS_LOS_DIAS = "Todos los días"

_TODOS_LOS_DIAS_RE = re.compile(r"\btodos\s*(?:los\s*)?d[ií]as\b", re.IGNORECASE)

_DIA_ALTERNATIVAS = r"(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bados?|domingos?)"
_DIA_PALABRA_RE = re.compile(r"\b" + _DIA_ALTERNATIVAS + r"\b", re.IGNORECASE)
_DIA_RANGO_RE = re.compile(
    r"\b(" + _DIA_ALTERNATIVAS + r")\s+a\s+(" + _DIA_ALTERNATIVAS + r")\b",
    re.IGNORECASE,
)


def _normalizar_palabra_dia(palabra):
    p = palabra.lower()
    if p.startswith("lu"):
        return "Lunes"
    if p.startswith("ma"):
        return "Martes"
    if p.startswith("mi"):
        return "Miércoles"
    if p.startswith("ju"):
        return "Jueves"
    if p.startswith("vi"):
        return "Viernes"
    if p.startswith("s"):
        return "Sábado"
    if p.startswith("d"):
        return "Domingo"
    return None


def _expandir_rango(inicio, fin):
    i = CANONICAL_DIAS.index(inicio)
    f = CANONICAL_DIAS.index(fin)
    if i <= f:
        return CANONICAL_DIAS[i:f + 1]
    return CANONICAL_DIAS[i:] + CANONICAL_DIAS[:f + 1]  # rango que da la vuelta a la semana


def extraer_dias(texto):
    if not texto:
        return []

    if _TODOS_LOS_DIAS_RE.search(texto):
        return [TODOS_LOS_DIAS]

    dias = set()
    rangos_consumidos = []

    for m in _DIA_RANGO_RE.finditer(texto):
        inicio = _normalizar_palabra_dia(m.group(1))
        fin = _normalizar_palabra_dia(m.group(2))
        if inicio and fin:
            dias.update(_expandir_rango(inicio, fin))
        rangos_consumidos.append((m.start(), m.end()))

    for m in _DIA_PALABRA_RE.finditer(texto):
        if any(m.start() >= s and m.end() <= e for s, e in rangos_consumidos):
            continue  # ya cubierto por un rango "X a Y"
        dia = _normalizar_palabra_dia(m.group(0))
        if dia:
            dias.add(dia)

    return sorted(dias, key=CANONICAL_DIAS.index)


# Categorías que en realidad son slugs/nombres de promoción, no una
# categoría real de beneficio.
_CATEGORIA_DENYLIST = {"dolares-premio"}
_CATEGORIA_MINUSCULAS = {"y", "de", "del", "la", "el", "en", "a", "los", "las"}


def normalizar_categoria(raw):
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    # Los slugs de promoción observados arrancan con un número
    # (ej. "40-de-descuento-visa"); no son una categoría real.
    if raw[0].isdigit() or raw.lower() in _CATEGORIA_DENYLIST:
        return None

    palabras = [p for p in re.split(r"[-\s]+", raw) if p]
    resultado = []
    for i, palabra in enumerate(palabras):
        lower = palabra.lower()
        if i > 0 and lower in _CATEGORIA_MINUSCULAS:
            resultado.append(lower)
        else:
            resultado.append(lower[:1].upper() + lower[1:])
    return " ".join(resultado) or None


# Mapeo de las ~23 categorías crudas (ya normalizadas a Title Case) al set
# consolidado de 8 que se usa en el sitio.
_CONSOLIDACION_CATEGORIA = {
    "Restaurantes y Bares": "Sabores",
    "Sabores": "Sabores",
    "Sabores Gourmet": "Sabores",
    "Cafeterias": "Sabores",
    "Comida Rapida": "Sabores",
    "Delivery": "Sabores",

    "Salud": "Salud y Belleza",
    "Belleza": "Salud y Belleza",

    "Entretención": "Entretención y Deportes",
    "Panoramas": "Entretención y Deportes",
    "Música": "Entretención y Deportes",
    "Cine": "Entretención y Deportes",
    "Deportes": "Entretención y Deportes",

    "Viajes": "Viajes",

    "Mascotas": "Mascotas",

    "Sustentable": "Sustentable",
    "Verdes": "Sustentable",

    "Cuotas Sin Interes": "Cuotas Sin Interés",

    "Beneficios y Descuentos": "Retail y Otras Marcas",
    "Descuentos": "Retail y Otras Marcas",
    "Otros": "Retail y Otras Marcas",
    "Catálogo Productos": "Retail y Otras Marcas",
    "Multiplica Millas": "Retail y Otras Marcas",
}

# Dentro de "Retail y Otras Marcas", comercios que en realidad son de
# viajes o de entretención/deportes: por palabra clave en el nombre...
_RETAIL_A_VIAJES_KEYWORDS_RE = re.compile(
    r"\b(?:hotel|spa|ski|tour|caba(?:ñ|n)a|resort|hostal|motel|"
    r"rent a car|aeropuerto|lounge|flixbus|transfer)\b",
    re.IGNORECASE,
)

# ...o por reconocimiento puntual, cuando el nombre no tiene ninguna
# palabra clave genérica (marcas de rent a car, centros de ski chilenos,
# actividades de aventura).
_RETAIL_A_VIAJES_MANUAL = {
    "hertz",
    "valle nevado",
    "el colorado - visa",
    "la parva - visa",
    "farellones - visa",
    "corralco - visa",
    "pillán - visa",
    "nevados de chillán - visa",
    "skydive colchagua",
    "zapping sport center",
}

_RETAIL_A_ENTRETENCION_MANUAL = {
    "ultimate fitness",
}


def consolidar_categoria(categoria, comercio=None):
    if not categoria:
        return None

    consolidada = _CONSOLIDACION_CATEGORIA.get(categoria, categoria)

    if consolidada == "Retail y Otras Marcas" and comercio:
        nombre = comercio.strip().lower()
        if nombre in _RETAIL_A_ENTRETENCION_MANUAL:
            return "Entretención y Deportes"
        if nombre in _RETAIL_A_VIAJES_MANUAL or _RETAIL_A_VIAJES_KEYWORDS_RE.search(comercio):
            return "Viajes"

    return consolidada


# Excepciones puntuales por nombre de comercio, sin importar de dónde
# haya salido la categoría (se aplica siempre, al final). Se revisaron a
# mano los 286 que habían quedado en "Retail y Otras Marcas" (texto
# completo de condiciones + búsqueda externa para los casos poco claros)
# y estos son los que en realidad son de otra categoría.
_CATEGORIA_MANUAL_OVERRIDE = {
    # producto de limpieza ecológica; "salud" es mención de paso en el texto
    "freemet": "Sustentable",
    # Banco de Chile: "Centro de Salud y Estética Integral"
    "carolina varela": "Salud y Belleza",
    # Santander: café/restaurant en Barrio Italia, Providencia (verificado
    # afuera del sitio, la descripción del beneficio no decía de qué era)
    "survenir": "Sabores",

    # --- Sabores: productos de comida/bebida, no solo restaurantes ---
    "alusweet": "Sabores",  # endulzantes naturales
    "aquality": "Sabores",  # pescados y mariscos congelados
    "atama": "Sabores",  # snacks de fruta
    "corrales del sur": "Sabores",  # "el mejor corte de carne"
    "fiamma": "Sabores",  # "desayunos, almuerzos y cenas"
    "gaetano": "Sabores",  # restaurante italiano
    "giullietta": "Sabores",  # restaurante italiano
    "mizos": "Sabores",  # snacks
    "quinto rumbo": "Sabores",  # "gastronomía y tradición chilena"
    "siamo coffee": "Sabores",  # café de especialidad
    "piwen": "Sabores",  # alimentos naturales
    "mercado carozzi": "Sabores",  # tienda online del fabricante de alimentos Carozzi

    # --- Salud y Belleza ---
    "zenclinic dental": "Salud y Belleza",
    "clínica abedules": "Salud y Belleza",  # clínica odontológica
    "gaes": "Salud y Belleza",  # audífonos/cuidado auditivo
    "uc christus": "Salud y Belleza",  # red de salud UC
    "cno": "Salud y Belleza",  # Cooperativa Nacional Odontológica
    "dbs": "Salud y Belleza",  # productos de belleza
    "the wow benefits": "Salud y Belleza",  # marca de belleza natural (verificado: thewowbenefits.cl)
    "tua": "Salud y Belleza",  # "belleza en potencia"

    # --- Viajes ---
    "mitta": "Viajes",  # arriendo de autos (el regex de "rent a car" no agarra el español)
    "mc parking": "Viajes",  # estacionamiento aeropuerto Pudahuel
    "ok parking express": "Viajes",  # estacionamiento aeropuerto Pudahuel + transfer
    "mcparking": "Viajes",  # estacionamiento Aeropuerto de Santiago
    "estacionamiento autopark": "Viajes",  # estacionamiento + traslados aeropuerto
    "viña vik": "Viajes",  # hotel + restaurantes + viñedo (caso límite, ver conversación)

    # --- Entretención y Deportes ---
    "slow life": "Entretención y Deportes",  # estudio de pilates y yoga
    "louis tomlinson": "Entretención y Deportes",  # concierto, Movistar Arena
    "visa - centro del vino concha y toro": "Entretención y Deportes",  # tour + degustación con entrada por temporada (caso límite)
}


# "Cuotas Sin Interés" y "Dólares-Premio" son ejes propios a propósito
# (el mecanismo del beneficio importa más que el rubro del comercio — ver
# conversación). Un override manual por nombre no debe pisarlos: el mismo
# nombre de comercio puede aparecer en un banco con ese tag y en el otro
# sin él (ej. GAES/UC CHRISTUS están en "Cuotas Sin Interés" del lado
# Santander pero sin categoría real del lado Banco de Chile).
_CATEGORIAS_PROTEGIDAS = {"Cuotas Sin Interés", "Dólares-Premio"}


def aplicar_categoria_manual(categoria, comercio):
    if categoria in _CATEGORIAS_PROTEGIDAS:
        return categoria
    # normaliza espacios repetidos (ej. "Clínica  Abedules" en la fuente)
    # para que el lookup no dependa de que quede igual de "prolijo"
    nombre = re.sub(r"\s+", " ", (comercio or "").strip().lower())
    return _CATEGORIA_MANUAL_OVERRIDE.get(nombre, categoria)


# Los que quedan sin categoría real son casos que normalizar_categoria()
# descarta a propósito por venir de un slug de promoción en vez de una
# categoría real (ver _CATEGORIA_DENYLIST / el chequeo de dígito inicial).
# Acá se rescatan los dos patrones grandes encontrados en Banco de Chile:
# "Dólares-Premio" en el nombre del comercio (catálogo de canje por
# consumo — categoría propia) y "restaurant" en el texto de condiciones
# (beneficio gastronómico que no traía Descripcion HTML con la palabra
# esperada en otro lado).
_DOLARES_PREMIO_RE = re.compile(r"d[oó]lares-premio", re.IGNORECASE)
_RESTAURANT_TEXTO_RE = re.compile(r"\brestaurant\b", re.IGNORECASE)


def completar_categoria_faltante(categoria, comercio, condiciones):
    if categoria:
        return categoria

    if _DOLARES_PREMIO_RE.search(comercio or ""):
        return "Dólares-Premio"

    texto_condiciones = " ".join(condiciones or [])
    if _RESTAURANT_TEXTO_RE.search(texto_condiciones):
        return "Sabores"

    return categoria


# Rescate específico de Santander: su propia taxonomía (tags "cat-*") no
# distingue mascotas, salud ni entretención — todo eso cae en el catch-all
# "cat-descuentos"/"cat-otros" (-> "Retail y Otras Marcas"). Se rescata
# leyendo la descripción real del beneficio en vez de adivinar por nombre
# de comercio (eso dio falsos positivos: "Petrizzio" es belleza, no
# mascotas; "Vita Fitness" es ropa deportiva, no un gimnasio).
#
# Ojo: esto NO se aplica al lado de Banco de Chile — su Descripcion es
# copy de marketing largo y la misma heurística ahí generó puro ruido
# (ej. "Intime", ropa interior, matcheaba "bienestar"; "The Wall", papel
# mural, matcheaba "estética"). Banco de Chile ya separa Salud y Mascotas
# bien en su propia categoría, así que no hace falta.
_MASCOTAS_TEXTO_RE = re.compile(
    r"\b(mascotas?|perros?|gatos?|canin[oa]s?|felin[oa]s?|veterinari[oa])\b",
    re.IGNORECASE,
)
_SALUD_BELLEZA_TEXTO_RE = re.compile(
    r"\b(bienestar|est[ée]tica|est[ée]tico|dental|odontolog[ií]a|dermo|"
    r"dermat[oó]log|capilar|kinesiolog[ií]a|cosm[ée]tic[oa]|cuidado personal|piel)\b",
    re.IGNORECASE,
)
_ENTRETENCION_TEXTO_RE = re.compile(r"\b(concierto|estadio|gira)\b", re.IGNORECASE)
# Mismo patrón que la regla de "restaurant" en Banco de Chile: boilerplate
# de "consumo en local" + dirección + tope de descuento que Santander usa
# para locales gastronómicos que no quedaron con el tag cat-sabores
# (confirmados a mano: Lil Silly Co es "Sushi, Comida Asiática y Poke" en
# Viña del Mar; La Membresía es un bar de hamburguesas en Osorno).
_CONSUMO_LOCAL_RE = re.compile(r"consumo en (?:el )?local\b", re.IGNORECASE)

# Marcas conocidas donde el texto no alcanza (la descripción no repite la
# palabra clave literal).
_RETAIL_A_MASCOTAS_MANUAL = {"petco"}


def rescatar_categoria_texto(categoria, comercio, texto):
    if categoria != "Retail y Otras Marcas":
        return categoria

    nombre = (comercio or "").strip().lower()
    if nombre in _RETAIL_A_MASCOTAS_MANUAL:
        return "Mascotas"

    texto = texto or ""
    if _MASCOTAS_TEXTO_RE.search(texto):
        return "Mascotas"
    if _CONSUMO_LOCAL_RE.search(texto):
        return "Sabores"
    if _SALUD_BELLEZA_TEXTO_RE.search(texto):
        return "Salud y Belleza"
    if _ENTRETENCION_TEXTO_RE.search(texto):
        return "Entretención y Deportes"

    return categoria


_TAG_RE = re.compile(r"<[^>]+>")


def _limpiar_fragmento_html(fragmento):
    texto = _TAG_RE.sub(" ", fragmento)
    texto = _html_module.unescape(texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


_LABEL_VACIO_RE = re.compile(r"^recuerda(?:\s+que)?\s*:?\s*$", re.IGNORECASE)


def html_a_bullets(html_str):
    if not html_str:
        return []

    # Captura tanto <p> como <li>, en orden de aparición: Santander suele
    # traer una frase introductoria suelta en un <p> antes del <ul> (ej.
    # "Sushi, Comida Asiática y Poke") que antes se perdía por extraer
    # solo los <li>.
    items = re.findall(r"<(?:p|li)[^>]*>(.*?)</(?:p|li)>", html_str, re.IGNORECASE | re.DOTALL)
    if not items:
        items = re.split(r"<br\s*/?>", html_str, flags=re.IGNORECASE)

    bullets = []
    for item in items:
        texto = _limpiar_fragmento_html(item)
        if not texto or _LABEL_VACIO_RE.match(texto):
            continue  # descarta el label suelto "Recuerda:" / "Recuerda que:"
        if bullets and bullets[-1] == texto:
            continue  # evita duplicar la misma frase
        bullets.append(texto)
    return bullets


_VACIO_RE = re.compile(r"^vacio$", re.IGNORECASE)
_COORD_RE = re.compile(r"^-?\d{1,3}\.\d+$")  # ej. "-33.4396403" (latitud/longitud sueltas)


def parse_sucursales_bancochile(raw_html):
    if not raw_html:
        return []

    items = re.findall(r"<li[^>]*>(.*?)</li>", raw_html, re.IGNORECASE | re.DOTALL)
    sucursales = []
    for item in items:
        texto = _limpiar_fragmento_html(item)
        partes = [p.strip() for p in texto.split(";")]
        partes = [
            p for p in partes
            if p and not _VACIO_RE.match(p) and not _COORD_RE.match(p)
        ]
        direccion = ", ".join(partes)
        if direccion:
            sucursales.append(direccion)
    return sucursales
