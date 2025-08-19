import streamlit as st
import pandas as pd
import altair as alt
import folium
from streamlit_folium import folium_static
import plotly.express as px
import plotly.graph_objects as go
import geopandas as gpd
import zipfile
import tempfile
import os
import io

# --- Título y Configuración General ---
st.set_page_config(layout="wide")
st.title(' ☔  Visor de Información Geoespacial de Precipitación  🌧️ ')
st.markdown("---")

# --- Funciones de Carga y Caching ---
@st.cache_data
def load_csv_data(uploaded_file_csv):
    """
    Carga y procesa el archivo CSV.
    Retorna el DataFrame o None en caso de error.
    """
    if uploaded_file_csv:
        try:
            df = pd.read_csv(uploaded_file_csv, sep=';')
            df = df.rename(columns={'Mpio': 'municipio', 'NOMBRE_VER': 'vereda'})
            st.success("Archivo CSV cargado exitosamente.")
            return df
        except Exception as e:
            st.error(f"Error al leer el archivo CSV: {e}")
            return None
    return None

@st.cache_data
def load_shapefile(uploaded_zip):
    """
    Extrae y carga el shapefile de un archivo ZIP.
    Retorna el GeoDataFrame o None en caso de error.
    """
    if uploaded_zip:
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                with zipfile.ZipFile(uploaded_zip, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                shp_files = [f for f in os.listdir(temp_dir) if f.endswith('.shp')]
                if shp_files:
                    shp_path = os.path.join(temp_dir, shp_files[0])
                    gdf = gpd.read_file(shp_path)
                    gdf.set_crs("EPSG:9377", inplace=True)
                    gdf = gdf.to_crs("EPSG:4326")
                    st.success("Archivos Shapefile cargados exitosamente.")
                    return gdf
                else:
                    st.error("No se encontró ningún archivo .shp en el archivo ZIP. Asegúrate de que el archivo .zip contenga al menos un .shp.")
                    return None
        except Exception as e:
            st.error(f"Error al procesar el archivo ZIP: {e}")
            return None
    return None

# --- Sección de Carga de Datos ---
with st.expander("📂 Cargar Datos"):
    st.write("Carga tu archivo `mapaCV.csv` y los archivos del shapefile (`.shp`, `.shx`, `.dbf`) comprimidos en un único archivo `.zip`.")
    uploaded_file_csv = st.file_uploader("Cargar archivo .csv (mapaCV.csv)", type="csv")
    uploaded_zip = st.file_uploader("Cargar shapefile (.zip)", type="zip")

df = load_csv_data(uploaded_file_csv)
gdf = load_shapefile(uploaded_zip)

if df is not None:
    required_cols = ['Nom_Est', 'Latitud', 'Longitud', 'municipio', 'Celda_XY', 'vereda', 'Id_estacion', 'departamento']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        st.error(f"Error: Las siguientes columnas requeridas no se encuentran en el archivo CSV: {', '.join(missing_cols)}. Por favor, verifica los nombres de las columnas en tu archivo.")
        df = None
    else:
        df['Latitud'] = pd.to_numeric(df['Latitud'], errors='coerce')
        df['Longitud'] = pd.to_numeric(df['Longitud'], errors='coerce')
        df.dropna(subset=['Latitud', 'Longitud'], inplace=True)
        if df.empty:
            st.error("El DataFrame está vacío. Por favor, asegúrate de que tu archivo CSV contenga datos válidos en las columnas 'Nom_Est', 'Latitud' y 'Longitud'.")
            df = None

if df is not None:
    # --- Sidebar de Filtrado (Sección 1: Opciones) ---
    st.sidebar.header("⚙️ Opciones de Filtrado")
    st.sidebar.markdown("---")

    # Selectores por municipio y celda
    municipios = sorted(df['municipio'].unique())
    selected_municipio = st.sidebar.multiselect("Elige uno o más municipios:", municipios)

    filtered_df_by_loc = df.copy()
    if selected_municipio:
        filtered_df_by_loc = filtered_df_by_loc[filtered_df_by_loc['municipio'].isin(selected_municipio)]
    
    celdas_by_municipio = sorted(filtered_df_by_loc['Celda_XY'].unique())
    selected_celda = st.sidebar.multiselect("Elige una o más celdas:", celdas_by_municipio)

    if selected_celda:
        filtered_df_by_loc = filtered_df_by_loc[filtered_df_by_loc['Celda_XY'].isin(selected_celda)]

    all_stations = sorted(filtered_df_by_loc['Nom_Est'].unique())

    # Controles de selección de estaciones
    with st.sidebar.expander("Seleccionar Estaciones"):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Seleccionar todas las estaciones"):
                st.session_state.selected_stations = all_stations
        with col2:
            if st.button("Limpiar selección"):
                st.session_state.selected_stations = []

        if 'selected_stations' not in st.session_state:
            st.session_state.selected_stations = []
        
        selected_stations_list = st.multiselect(
            "Estaciones disponibles:",
            options=all_stations,
            default=st.session_state.selected_stations
        )
        st.session_state.selected_stations = selected_stations_list

    selected_stations_df = df[df['Nom_Est'].isin(selected_stations_list)]

    start_year, end_year = st.sidebar.slider(
        "Elige el rango de años:",
        min_value=1970,
        max_value=2021,
        value=(1970, 2021)
    )
    years_to_analyze = [str(year) for year in range(start_year, end_year + 1)]
    years_to_analyze_present = [year for year in years_to_analyze if year in selected_stations_df.columns]
    
    # --- Pestañas de la Aplicación ---
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Datos Tabulados",
        "📈 Gráficos de Precipitación",
        "🌎 Mapa de Estaciones",
        "🎬 Animación de Lluvia"
    ])

    # --- Pestaña 1: Datos Tabulados ---
    with tab1:
        st.header("📊 Datos Tabulados de las Estaciones")
        st.markdown("---")
        if selected_stations_df.empty:
            st.info("Por favor, selecciona al menos una estación en la barra lateral.")
        else:
            st.subheader("Información básica de las Estaciones Seleccionadas")
            info_cols = ['Nom_Est', 'Id_estacion', 'porc_datos', 'departamento', 'municipio', 'vereda', 'Celda_XY']
            cols_to_display = [col for col in info_cols + years_to_analyze_present if col in df.columns]
            df_to_display = selected_stations_df[cols_to_display].set_index('Nom_Est')

            if not df_to_display.empty and years_to_analyze_present:
                try:
                    styled_df = df_to_display.style.background_gradient(cmap='RdYlBu_r', subset=years_to_analyze_present)
                    st.dataframe(styled_df)
                except Exception as e:
                    st.error(f"Error al aplicar estilo de tabla: {e}. Mostrando tabla sin estilo.")
                    st.dataframe(df_to_display)
            else:
                st.dataframe(df_to_display)
            
            st.subheader("Estadísticas de Precipitación")
            stats_df = selected_stations_df[['Nom_Est', 'Id_estacion', 'municipio', 'vereda']].copy()

            if years_to_analyze_present and not selected_stations_df.empty:
                stats_df['Precipitación Máxima (mm)'] = selected_stations_df[years_to_analyze_present].max(axis=1).round(2)
                stats_df['Año Máximo'] = selected_stations_df[years_to_analyze_present].idxmax(axis=1)
                stats_df['Precipitación Mínima (mm)'] = selected_stations_df[years_to_analyze_present].min(axis=1).round(2)
                stats_df['Año Mínimo'] = selected_stations_df[years_to_analyze_present].idxmin(axis=1)
                stats_df['Precipitación Media (mm)'] = selected_stations_df[years_to_analyze_present].mean(axis=1).round(2)
                stats_df['Desviación Estándar'] = selected_stations_df[years_to_analyze_present].std(axis=1).round(2)

                df_melted_stats = selected_stations_df.melt(
                    id_vars=['Nom_Est'],
                    value_vars=years_to_analyze_present,
                    var_name='Año',
                    value_name='Precipitación'
                )

                if not df_melted_stats.empty:
                    summary_row = pd.DataFrame([{
                        'Nom_Est': 'Todas las estaciones',
                        'Id_estacion': '',
                        'municipio': '',
                        'vereda': '',
                        'Precipitación Máxima (mm)': df_melted_stats['Precipitación'].max(),
                        'Año Máximo': df_melted_stats.loc[df_melted_stats['Precipitación'].idxmax(), 'Año'],
                        'Precipitación Mínima (mm)': df_melted_stats['Precipitación'].min(),
                        'Año Mínimo': df_melted_stats.loc[df_melted_stats['Precipitación'].idxmin(), 'Año'],
                        'Precipitación Media (mm)': df_melted_stats['Precipitación'].mean().round(2),
                        'Desviación Estándar': df_melted_stats['Precipitación'].std().round(2)
                    }])
                    stats_df = pd.concat([stats_df, summary_row], ignore_index=True)
                
                st.dataframe(stats_df.set_index('Nom_Est'))

    # --- Pestaña 2: Gráficos de Precipitación ---
    with tab2:
        st.header("📈 Gráficos de Precipitación")
        st.markdown("---")
        if selected_stations_df.empty:
            st.info("Por favor, selecciona al menos una estación en la barra lateral.")
        else:
            df_melted = selected_stations_df.melt(
                id_vars=['Nom_Est'],
                value_vars=years_to_analyze_present,
                var_name='Año',
                value_name='Precipitación'
            )
            df_melted['Año'] = df_melted['Año'].astype(int)

            # Controles para el eje vertical
            st.subheader("Opciones de Eje Vertical (Y)")
            axis_control = st.radio("Elige el control del eje Y:", ('Automático', 'Personalizado'))
            y_range = None
            if axis_control == 'Personalizado':
                min_precip = df_melted['Precipitación'].min()
                max_precip = df_melted['Precipitación'].max()
                min_y = st.number_input("Valor mínimo del eje Y:", value=float(min_precip), format="%.2f")
                max_y = st.number_input("Valor máximo del eje Y:", value=float(max_precip), format="%.2f")
                if min_y >= max_y:
                    st.warning("El valor mínimo debe ser menor que el valor máximo.")
                else:
                    y_range = (min_y, max_y)

            st.subheader("Precipitación Anual por Estación")
            chart_type = st.radio("Elige el tipo de gráfico:", ('Líneas', 'Barras'))
            y_scale = alt.Scale(domain=y_range) if y_range else alt.Scale()
            if chart_type == 'Líneas':
                chart = alt.Chart(df_melted).mark_line(point=True).encode(
                    x=alt.X('Año:O', title='Año', axis=alt.Axis(format='d')),
                    y=alt.Y('Precipitación:Q', title='Precipitación (mm)', scale=y_scale),
                    color=alt.Color('Nom_Est', title='Estación'),
                    tooltip=['Nom_Est', 'Año', 'Precipitación']
                ).interactive()
            else:
                chart = alt.Chart(df_melted).mark_bar().encode(
                    x=alt.X('Año:O', title='Año', axis=alt.Axis(format='d')),
                    y=alt.Y('Precipitación:Q', title='Precipitación (mm)', scale=y_scale),
                    color=alt.Color('Nom_Est', title='Estación'),
                    tooltip=['Nom_Est', 'Año', 'Precipitación']
                ).interactive()
            st.altair_chart(chart, use_container_width=True)

            st.subheader("Comparación de Precipitación entre Estaciones")
            compare_year = st.selectbox(
                "Selecciona el año para comparar:",
                options=years_to_analyze_present
            )
            sort_order = st.radio("Ordenar por:", ('Mayor a menor', 'Menor a mayor'))

            df_compare = selected_stations_df[['Nom_Est', compare_year]].copy()
            df_compare = df_compare.rename(columns={compare_year: 'Precipitación'})
            if sort_order == 'Mayor a menor':
                df_compare = df_compare.sort_values(by='Precipitación', ascending=False)
            else:
                df_compare = df_compare.sort_values(by='Precipitación', ascending=True)
            
            fig_bar = px.bar(
                df_compare,
                x='Nom_Est',
                y='Precipitación',
                title=f'Precipitación en el año {compare_year}',
                labels={'Nom_Est': 'Estación', 'Precipitación': 'Precipitación (mm)'},
                range_y=y_range
            )
            st.plotly_chart(fig_bar, use_container_width=True)

            st.subheader("Análisis de Distribución (Box Plot)")
            if not df_melted.empty:
                fig_box = px.box(
                    df_melted,
                    x='Nom_Est',
                    y='Precipitación',
                    title='Distribución de Precipitación por Estación',
                    labels={'Nom_Est': 'Estación', 'Precipitación': 'Precipitación (mm)'},
                    range_y=y_range
                )
                st.plotly_chart(fig_box, use_container_width=True)
            else:
                st.info("No hay datos para generar el gráfico de caja.")

    # --- Pestaña 3: Mapa ---
    with tab3:
        st.header("🌎 Mapa de Ubicación de las Estaciones")
        st.markdown("---")

        if gdf is None:
            st.info("Por favor, carga el archivo shapefile en formato .zip en la sección 'Cargar Datos'.")
        elif selected_stations_df.empty:
            st.info("Por favor, selecciona al menos una estación en la barra lateral.")
        else:
            # Botones para centrar el mapa
            col_map1, col_map2, col_map3 = st.columns(3)
            with col_map1:
                if st.button("Centrar en Colombia"):
                    st.session_state.map_center_type = 'colombia'
            with col_map2:
                if st.button("Centrar en Antioquia"):
                    st.session_state.map_center_type = 'antioquia'
            with col_map3:
                if st.button("Centrar en Estaciones Seleccionadas"):
                    st.session_state.map_center_type = 'stations'

            if 'map_center_type' not in st.session_state:
                st.session_state.map_center_type = 'stations'

            map_center = [4.5709, -74.2973]
            zoom_level = 6

            gdf_selected = gdf[gdf['Nom_Est'].isin(selected_stations_list)]

            if st.session_state.map_center_type == 'antioquia':
                map_center = [6.2442, -75.5812]
                zoom_level = 8
            elif st.session_state.map_center_type == 'stations' and not gdf_selected.empty:
                map_center = [gdf_selected.geometry.centroid.y.mean(), gdf_selected.geometry.centroid.x.mean()]
                zoom_level = 8
            
            m = folium.Map(location=map_center, zoom_start=zoom_level, tiles="CartoDB positron")

            if st.session_state.map_center_type == 'stations' and not gdf_selected.empty:
                bounds = [[gdf_selected.total_bounds[1], gdf_selected.total_bounds[0]],
                          [gdf_selected.total_bounds[3], gdf_selected.total_bounds[2]]]
                m.fit_bounds(bounds)
            
            gdf_selected = gdf_selected.merge(selected_stations_df[['Nom_Est', 'Latitud', 'Longitud']], on='Nom_Est', how='left')
            
            if years_to_analyze_present:
                stats_df = selected_stations_df.melt(
                    id_vars=['Nom_Est'],
                    value_vars=years_to_analyze_present,
                    var_name='Año',
                    value_name='Precipitación'
                ).groupby('Nom_Est')['Precipitación'].mean().reset_index()
                stats_df.rename(columns={'Precipitación': 'Precipitación Media (mm)'}, inplace=True)
                gdf_selected = gdf_selected.merge(stats_df, on='Nom_Est', how='left')

            if not gdf_selected.empty:
                folium.GeoJson(
                    gdf_selected.to_json(),
                    name='Áreas del Shapefile',
                    tooltip=folium.features.GeoJsonTooltip(fields=['Nom_Est', 'municipio', 'vereda', 'Precipitación Media (mm)'],
                                                            aliases=['Estación', 'Municipio', 'Vereda', 'Precipitación Media'],
                                                            style=("background-color: white; color: #333333; font-family: sans-serif; font-size: 12px; padding: 10px;"))
                ).add_to(m)

                for idx, row in gdf_selected.iterrows():
                    if pd.notna(row['Latitud']) and pd.notna(row['Longitud']):
                        pop_up_text = (
                            f"<b>Estación:</b> {row['Nom_Est']}<br>"
                            f"<b>Municipio:</b> {row['municipio']}<br>"
                            f"<b>Vereda:</b> {row['vereda']}<br>"
                            f"<b>Precipitación Media:</b> {row.get('Precipitación Media (mm)', 'N/A'):.2f} mm"
                        )
                        tooltip_text = f"Estación: {row['Nom_Est']}"
                        folium.CircleMarker(
                            location=[row['Latitud'], row['Longitud']],
                            radius=6,
                            popup=pop_up_text,
                            tooltip=tooltip_text,
                            color='blue',
                            fill=True,
                            fill_color='blue',
                            fill_opacity=0.6
                        ).add_to(m)
            folium_static(m)

    # --- Pestaña 4: Animaciones ---
    with tab4:
        st.header("🎬 Animación de Precipitación Anual")
        st.markdown("---")
        if selected_stations_df.empty:
            st.info("Por favor, selecciona al menos una estación en la barra lateral.")
        else:
            animation_type = st.radio("Selecciona el tipo de animación:", ('Barras Animadas', 'Mapa Animado'))
            if years_to_analyze_present:
                if animation_type == 'Barras Animadas':
                    df_melted_anim = selected_stations_df.melt(
                        id_vars=['Nom_Est'],
                        value_vars=years_to_analyze_present,
                        var_name='Año',
                        value_name='Precipitación'
                    )
                    df_melted_anim['Año'] = df_melted_anim['Año'].astype(str)
                    
                    fig = px.bar(
                        df_melted_anim,
                        x='Nom_Est',
                        y='Precipitación',
                        animation_frame='Año',
                        color='Nom_Est',
                        title='Precipitación Anual por Estación',
                        labels={'Nom_Est': 'Estación', 'Precipitación': 'Precipitación (mm)'},
                        range_y=y_range
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else: # Mapa Animado
                    df_melted_map = selected_stations_df.melt(
                        id_vars=['Nom_Est', 'Latitud', 'Longitud'],
                        value_vars=years_to_analyze_present,
                        var_name='Año',
                        value_name='Precipitación'
                    )
                    fig = px.scatter_mapbox(
                        df_melted_map,
                        lat="Latitud",
                        lon="Longitud",
                        hover_name="Nom_Est",
                        hover_data={"Precipitación": True, "Año": True, "Latitud": False, "Longitud": False},
                        color="Precipitación",
                        size="Precipitación",
                        color_continuous_scale=px.colors.sequential.Bluyl,
                        animation_frame="Año",
                        mapbox_style="open-street-map",
                        zoom=7,
                        title="Precipitación Anual Animada en el Mapa",
                        range_color=y_range
                    )
                    fig.update_layout(
                        mapbox_style="open-street-map",
                        mapbox_zoom=7,
                        mapbox_center={"lat": df_melted_map['Latitud'].mean(), "lon": df_melted_map['Longitud'].mean()},
                    )
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("El rango de años seleccionado no contiene datos de precipitación para las estaciones seleccionadas. Por favor, ajusta el rango de años.")
