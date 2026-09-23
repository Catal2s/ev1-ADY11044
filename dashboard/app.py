"""
Dashboard StreamView Analytics — Calidad del catálogo de películas y series
Asignatura ADY1104 Visualización de Datos

Para ejecutarlo (desde la carpeta raíz del proyecto):
    pip install -r requirements.txt
    streamlit run dashboard/app.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ------------------------------------------------------------------
# Configuración general
# ------------------------------------------------------------------
st.set_page_config(page_title='StreamView Analytics', page_icon='🎬', layout='wide')

# Misma paleta que el notebook: gris para el contexto, color solo para lo que se destaca
GRIS = '#B8B8B8'
BUENO = '#2A9D8F'
MALO = '#E76F51'
TEXTO_SUAVE = '#555555'
UMBRAL_BUENO = 7  # nota desde la que consideramos un título "bien evaluado"

TRADUCCION_GENEROS = {
    'Drama': 'Drama', 'Comedy': 'Comedia', 'Thriller': 'Suspenso', 'Action': 'Acción',
    'Horror': 'Terror', 'Romance': 'Romance', 'Crime': 'Crimen', 'Adventure': 'Aventura',
    'Animation': 'Animación', 'Family': 'Familia', 'Science Fiction': 'Ciencia ficción',
    'Fantasy': 'Fantasía', 'Documentary': 'Documental', 'Mystery': 'Misterio',
    'History': 'Historia', 'Music': 'Música', 'War': 'Bélico', 'Western': 'Western',
    'TV Movie': 'Película de TV', 'Action & Adventure': 'Acción y aventura',
    'Sci-Fi & Fantasy': 'Ciencia ficción y fantasía', 'Reality': 'Reality',
    'Kids': 'Infantil', 'Talk': 'Conversación', 'Soap': 'Teleserie',
    'War & Politics': 'Guerra y política', 'News': 'Noticias', 'Unknown': 'Sin clasificar',
}

IDIOMAS = {
    'en': 'Inglés', 'zh': 'Chino', 'ja': 'Japonés', 'ko': 'Coreano', 'es': 'Español',
    'fr': 'Francés', 'de': 'Alemán', 'hi': 'Hindi', 'tl': 'Tagalo', 'pt': 'Portugués',
    'ru': 'Ruso', 'it': 'Italiano', 'tr': 'Turco', 'ar': 'Árabe', 'nl': 'Neerlandés',
    'cn': 'Cantonés', 'th': 'Tailandés', 'pl': 'Polaco',
}


# ------------------------------------------------------------------
# Carga y limpieza (misma lógica que el notebook)
# ------------------------------------------------------------------
def buscar_archivo(nombre):
    """Busca el CSV en data/ o en la carpeta raíz, se ejecute desde donde se ejecute."""
    base = Path(__file__).resolve().parent
    candidatos = [base.parent / 'data' / nombre, base / 'data' / nombre,
                  base.parent / nombre, base / nombre, Path('data') / nombre, Path(nombre)]
    for ruta in candidatos:
        if ruta.exists():
            return ruta
    st.error(f'No se encontró {nombre}. Déjalo en la carpeta data/ del proyecto.')
    st.stop()


@st.cache_data
def cargar_datos():
    peliculas = pd.read_csv(buscar_archivo('netflix_movies_detailed_up_to_2025.csv'))
    series = pd.read_csv(buscar_archivo('netflix_tv_shows_detailed_up_to_2025.csv'))
    peliculas['tipo'] = 'Películas'
    series['tipo'] = 'Series'

    df = pd.concat([peliculas, series], ignore_index=True)
    df = df.dropna(subset=['title']).drop_duplicates(subset=['tipo', 'show_id'])
    df.loc[df['rating'] == 0, 'rating'] = np.nan  # rating 0 = sin votos
    df = df.drop(columns=['duration', 'vote_average', 'budget', 'revenue', 'date_added'], errors='ignore')

    df['idioma'] = df['language'].map(IDIOMAS).fillna('Otros')
    df['lista_generos'] = (df['genres'].fillna('Unknown').str.split(', ')
                           .apply(lambda gs: [TRADUCCION_GENEROS.get(g, g) for g in gs]))
    df['generos_texto'] = df['lista_generos'].str.join(', ')
    return df


datos = cargar_datos()

# ------------------------------------------------------------------
# Filtros (barra lateral)
# ------------------------------------------------------------------
st.sidebar.header('Filtros')

OPCIONES_TIPO = {'Ambos': ['Películas', 'Series'], 'Solo películas': ['Películas'], 'Solo series': ['Series']}
opcion_tipo = st.sidebar.radio('Tipo de contenido', list(OPCIONES_TIPO))
tipos = OPCIONES_TIPO[opcion_tipo]

anio_min, anio_max = int(datos['release_year'].min()), int(datos['release_year'].max())
anios = st.sidebar.slider('Año de estreno', anio_min, anio_max, (anio_min, anio_max))

todos_generos = sorted({g for gs in datos['lista_generos'] for g in gs})
generos = st.sidebar.multiselect('Géneros', todos_generos, placeholder='Todos los géneros')

orden_idiomas = list(IDIOMAS.values()) + ['Otros']
idiomas = st.sidebar.multiselect('Idioma original', orden_idiomas, placeholder='Todos los idiomas')

min_votos = st.sidebar.select_slider(
    'Mínimo de votos por título', options=[0, 10, 20, 50, 100, 200, 500], value=50,
    help='Con pocos votos el rating depende de muy pocas personas. Por defecto usamos 50, '
         'igual que en el notebook.')

st.sidebar.caption('Los indicadores comparan la selección contra el catálogo completo '
                   'con el mismo mínimo de votos.')

# Base de comparación: todo el catálogo con el mismo mínimo de votos
base = datos[datos['rating'].notna() & (datos['vote_count'] >= min_votos)]

filtro = base[base['tipo'].isin(tipos) & base['release_year'].between(*anios)]
if generos:
    filtro = filtro[filtro['lista_generos'].apply(lambda gs: any(g in generos for g in gs))]
if idiomas:
    filtro = filtro[filtro['idioma'].isin(idiomas)]

# ------------------------------------------------------------------
# Encabezado y KPIs
# ------------------------------------------------------------------
st.title('Calidad del catálogo de StreamView')
st.caption('¿Qué contenido tiene más probabilidad de dejar conforme al usuario? '
           'Dashboard para el equipo de contenidos y adquisiciones.')

if filtro.empty:
    st.warning('No hay títulos con esta combinación de filtros. Prueba ampliando la selección.')
    st.stop()


def fmt(numero, decimales=0):
    """Formato chileno: punto de miles y coma decimal."""
    texto = f'{numero:,.{decimales}f}'
    return texto.replace(',', 'X').replace('.', ',').replace('X', '.')


pct_bueno = (filtro['rating'] >= UMBRAL_BUENO).mean() * 100
pct_bueno_base = (base['rating'] >= UMBRAL_BUENO).mean() * 100
mediana = filtro['rating'].median()
mediana_base = base['rating'].median()

# La comparación contra el catálogo solo tiene sentido si hay algún filtro aplicado
hay_filtros = (opcion_tipo != 'Ambos' or anios != (anio_min, anio_max)
               or bool(generos) or bool(idiomas))

k1, k2, k3, k4 = st.columns(4)
k1.metric('Títulos en la selección', fmt(len(filtro)),
          f'{fmt(len(filtro) / len(base) * 100, 1)}% del catálogo' if hay_filtros else None,
          delta_color='off')
k2.metric('Rating mediano', fmt(mediana, 1),
          f'{fmt(mediana - mediana_base, 1)} vs catálogo' if hay_filtros else None)
k3.metric(f'% bien evaluados (≥ {UMBRAL_BUENO})', f'{fmt(pct_bueno, 1)}%',
          f'{fmt(pct_bueno - pct_bueno_base, 1)} pts vs catálogo' if hay_filtros else None)
k4.metric('Votos totales', fmt(filtro['vote_count'].sum()))
if not hay_filtros:
    st.caption('Mostrando el catálogo completo. Aplica filtros para compararlos contra el total.')

# ------------------------------------------------------------------
# Funciones de apoyo para los gráficos
# ------------------------------------------------------------------
def estilo(fig, titulo, subtitulo, alto=500):
    fig.update_layout(
        title=dict(text=f'<b>{titulo}</b><br><span style="font-size:15px;color:{TEXTO_SUAVE}">'
                        f'{subtitulo}</span>', x=0, xanchor='left', font=dict(size=20)),
        template='simple_white', height=alto, margin=dict(l=10, r=40, t=110, b=50),
        font=dict(size=15), showlegend=False,
        hoverlabel=dict(font_size=14),
    )
    fig.update_xaxes(tickfont=dict(size=14), title_font=dict(size=15))
    fig.update_yaxes(tickfont=dict(size=15), title_font=dict(size=15))
    return fig


def linea_referencia(fig, x, texto):
    """Línea vertical punteada con su etiqueta arriba del área del gráfico, sin tapar los datos."""
    fig.add_shape(type='line', x0=x, x1=x, y0=0, y1=1, xref='x', yref='paper',
                  line=dict(color='#444444', width=1.5, dash='dash'), layer='above')
    fig.add_annotation(x=x, y=1, xref='x', yref='paper', yanchor='bottom', yshift=4,
                       text=texto, showarrow=False, font=dict(size=13, color='#444444'))


def colores_destacados(indices):
    """Primero de la lista en verde, último en rojo, el resto en gris."""
    return [BUENO if i == 0 else MALO if i == len(indices) - 1 else GRIS for i in range(len(indices))]


por_genero = filtro.explode('lista_generos').rename(columns={'lista_generos': 'genero'})
por_genero = por_genero[por_genero['genero'] != 'Sin clasificar']
if generos:
    por_genero = por_genero[por_genero['genero'].isin(generos)]

# ------------------------------------------------------------------
# Navegación por pestañas
# ------------------------------------------------------------------
tab_resumen, tab_generos, tab_tiempo, tab_titulos = st.tabs(
    ['Resumen', 'Géneros en detalle', 'Evolución en el tiempo', 'Explorar títulos'])

# ---------------- Resumen ----------------
with tab_resumen:
    col_izq, col_der = st.columns([1.1, 1])

    with col_izq:
        top_n = 10
        resumen = (por_genero.groupby('genero')
                   .agg(n=('rating', 'size'), pct=('rating', lambda x: (x >= UMBRAL_BUENO).mean() * 100))
                   .query('n >= 30')
                   .nlargest(top_n, 'n')
                   .sort_values('pct', ascending=False))
        if resumen.empty:
            st.info('No hay géneros con al menos 30 títulos en la selección.')
        else:
            fig = go.Figure(go.Bar(
                x=resumen['pct'], y=resumen.index, orientation='h',
                marker_color=colores_destacados(resumen.index),
                text=[f'{fmt(v)}%' for v in resumen['pct']], textposition='outside', textfont=dict(size=15),
                customdata=resumen['n'],
                hovertemplate='<b>%{y}</b><br>%{x:.1f}% bien evaluados<br>%{customdata} títulos<extra></extra>'))
            linea_referencia(fig, pct_bueno, f'Selección: {fmt(pct_bueno)}%')
            fig.update_yaxes(autorange='reversed', title=None)
            fig.update_xaxes(title=f'% de títulos con rating ≥ {UMBRAL_BUENO}',
                             range=[0, resumen['pct'].max() * 1.18])
            mejor, peor = resumen.index[0], resumen.index[-1]
            titulo_barras = (f'{mejor} lidera; {peor} queda al final' if len(resumen) > 1
                             else f'{mejor}: {fmt(resumen["pct"].iloc[0])}% de títulos bien evaluados')
            st.plotly_chart(estilo(fig, titulo_barras,
                                   f'% de títulos bien evaluados por género (top {len(resumen)} por cantidad)'),
                            width='stretch')

    with col_der:
        comp = filtro.groupby('tipo')['rating'].agg(
            mediana='median', pct=lambda x: (x >= UMBRAL_BUENO).mean() * 100, n='size').reset_index()
        fig = go.Figure(go.Bar(
            x=comp['tipo'], y=comp['pct'],
            marker_color=[BUENO if t == comp.loc[comp['pct'].idxmax(), 'tipo'] else GRIS for t in comp['tipo']],
            text=[f'{fmt(v)}%' for v in comp['pct']], textposition='outside', textfont=dict(size=16), width=0.5,
            customdata=np.stack([comp['mediana'], comp['n']], axis=1),
            hovertemplate='<b>%{x}</b><br>%{y:.1f}% bien evaluados<br>'
                          'Mediana: %{customdata[0]:.1f}<br>%{customdata[1]} títulos<extra></extra>'))
        fig.update_yaxes(title=f'% con rating ≥ {UMBRAL_BUENO}', range=[0, max(comp['pct'].max() * 1.2, 10)])
        fig.update_xaxes(title=None)
        st.plotly_chart(estilo(fig, 'Películas vs series', 'Porcentaje de títulos bien evaluados por tipo'),
                        width='stretch')

    nota = (f'Se consideran solo títulos con al menos {min_votos} votos. '
            'Un título con varios géneros cuenta en cada uno de ellos.')
    if opcion_tipo == 'Ambos':
        nota += ('  Los porcentajes por género incluyen películas y series; como las series se '
                 'evalúan más alto, los valores son mayores que en el análisis del notebook '
                 '(solo películas). Elige "Solo películas" para comparar directamente.')
    st.caption(nota)

# ---------------- Géneros en detalle ----------------
with tab_generos:
    cantidad = st.slider('Cantidad de géneros a mostrar (los con más títulos)', 5, 20, 10)
    conteo = por_genero['genero'].value_counts()
    elegidos = conteo[conteo >= 30].head(cantidad).index
    datos_box = por_genero[por_genero['genero'].isin(elegidos)]

    if datos_box.empty:
        st.info('No hay géneros con al menos 30 títulos en la selección.')
    else:
        orden = datos_box.groupby('genero')['rating'].median().sort_values(ascending=False).index.tolist()
        mapa = {g: (BUENO if i == 0 else MALO if i == len(orden) - 1 else GRIS) for i, g in enumerate(orden)}
        fig = px.box(datos_box, x='rating', y='genero', color='genero', color_discrete_map=mapa,
                     category_orders={'genero': orden}, points='outliers',
                     hover_data={'title': True, 'genero': False})
        fig.update_traces(marker=dict(size=3, opacity=0.35), line=dict(width=1.3))
        linea_referencia(fig, filtro['rating'].median(), f'Mediana selección: {fmt(filtro["rating"].median(), 1)}')
        fig.update_xaxes(title='Rating (0–10)', range=[1, 10])
        fig.update_yaxes(title=None)
        titulo_box = (f'{orden[0]} es el género mejor evaluado; {orden[-1]} el más bajo' if len(orden) > 1
                      else f'Distribución del rating en {orden[0]}')
        st.plotly_chart(estilo(fig, titulo_box,
                               'Distribución del rating por género, ordenado por mediana', alto=560),
                        width='stretch')

        tabla = (datos_box.groupby('genero')['rating']
                 .agg(Títulos='size', Mediana='median',
                      Q1=lambda x: x.quantile(0.25), Q3=lambda x: x.quantile(0.75),
                      **{'% ≥ 7': lambda x: (x >= UMBRAL_BUENO).mean() * 100})
                 .loc[orden])
        tabla['Rango intercuartil'] = tabla['Q3'] - tabla['Q1']
        with st.expander('Ver tabla con los valores'):
            st.dataframe(tabla.round(2), width='stretch')

# ---------------- Evolución en el tiempo ----------------
with tab_tiempo:
    tendencia = filtro.groupby(['release_year', 'tipo'])['rating'].median().reset_index()
    fig = go.Figure()
    for tipo, color in [('Series', BUENO), ('Películas', GRIS)]:
        d = tendencia[tendencia['tipo'] == tipo]
        if d.empty:
            continue
        fig.add_trace(go.Scatter(
            x=d['release_year'], y=d['rating'], mode='lines+markers', name=tipo,
            line=dict(color=color, width=3), marker=dict(size=7),
            hovertemplate=f'<b>{tipo}</b><br>%{{x}}: mediana %{{y:.2f}}<extra></extra>'))
        fig.add_annotation(x=d['release_year'].iloc[-1], y=d['rating'].iloc[-1], text=f'<b>{tipo}</b>',
                           xanchor='left', xshift=10, showarrow=False,
                           font=dict(color=color if tipo == 'Series' else '#888'))

    subtitulo = 'Rating mediano por año de estreno'
    titulo = 'Evolución del rating por año'
    if set(tendencia['tipo']) == {'Películas', 'Series'}:
        piv = tendencia.pivot(index='release_year', columns='tipo', values='rating').dropna()
        brecha = (piv['Series'] - piv['Películas']).mean()
        titulo = (f'Las series se evalúan {fmt(abs(brecha), 1)} puntos '
                  f'{"mejor" if brecha > 0 else "peor"} que las películas')
        subtitulo += ' — brecha promedio en el período seleccionado'
    fig.update_xaxes(title='Año de estreno', dtick=1)
    # Rango calculado con los datos (con un mínimo de amplitud) para que ningún punto quede fuera
    lo, hi = tendencia['rating'].min(), tendencia['rating'].max()
    margen = max((hi - lo) * 0.15, 0.3)
    fig.update_yaxes(title='Rating mediano (0–10)', range=[max(lo - margen, 0), min(hi + margen, 10)])
    st.plotly_chart(estilo(fig, titulo, subtitulo), width='stretch')
    st.caption('El eje vertical no parte en 0 y se ajusta a los datos filtrados, para que se vea la '
               'variación entre años; lo que se compara es la distancia entre las líneas.')

# ---------------- Explorar títulos ----------------
with tab_titulos:
    st.markdown('Cada punto es un título. Pasa el mouse para ver el detalle o selecciona un área para hacer zoom.')
    MAX_PUNTOS = 4000  # sobre esto el gráfico se vuelve lento y los puntos se tapan entre sí
    muestra = filtro.sample(min(len(filtro), MAX_PUNTOS), random_state=1)
    fig = px.scatter(muestra, x='popularity', y='rating', color='tipo', log_x=True, opacity=0.5,
                     color_discrete_map={'Series': BUENO, 'Películas': GRIS},
                     hover_data={'title': True, 'release_year': True, 'generos_texto': True,
                                 'vote_count': True, 'popularity': ':.1f', 'tipo': False})
    fig.update_traces(marker=dict(size=6))
    fig.update_layout(legend=dict(title=None, orientation='h', y=1.02, x=1, xanchor='right'))
    fig.update_xaxes(title='Popularidad (escala logarítmica)')
    fig.update_yaxes(title='Rating (0–10)')
    validos = filtro[filtro['popularity'] > 0]
    corr = np.corrcoef(np.log(validos['popularity']), validos['rating'])[0, 1] if len(validos) >= 3 else np.nan
    texto_corr = 'no disponible con tan pocos títulos' if np.isnan(corr) else fmt(corr, 2)
    fig = estilo(fig, 'Lo más popular no siempre es lo mejor evaluado',
                 f'Popularidad vs rating (correlación: {texto_corr})', alto=500)
    fig.update_layout(showlegend=True)
    st.plotly_chart(fig, width='stretch')
    if len(filtro) > MAX_PUNTOS:
        st.caption(f'Para que el gráfico cargue rápido se muestra una muestra aleatoria de '
                   f'{fmt(MAX_PUNTOS)} de los {fmt(len(filtro))} títulos. La correlación se calcula '
                   f'con todos los títulos de la selección.')

    st.subheader('Ranking de títulos')
    busqueda = st.text_input('Buscar por nombre', placeholder='Ej: Inception')
    ranking = filtro.copy()
    if busqueda:
        ranking = ranking[ranking['title'].str.contains(busqueda, case=False, na=False, regex=False)]
    ranking = (ranking.sort_values(['rating', 'vote_count'], ascending=False)
               [['title', 'tipo', 'release_year', 'generos_texto', 'idioma', 'rating', 'vote_count']]
               .rename(columns={'title': 'Título', 'tipo': 'Tipo', 'release_year': 'Año',
                                'generos_texto': 'Géneros', 'idioma': 'Idioma',
                                'rating': 'Rating', 'vote_count': 'Votos'}))
    if ranking.empty:
        st.info('Ningún título coincide con la búsqueda.')
    else:
        st.dataframe(ranking.head(100), width='stretch', hide_index=True,
                     column_config={'Rating': st.column_config.ProgressColumn(
                         'Rating', min_value=0, max_value=10, format='%.1f')})
        st.caption(f'Mostrando los {fmt(min(len(ranking), 100))} mejores de {fmt(len(ranking))} títulos.')
