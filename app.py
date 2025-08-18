import streamlit as st
import pandas as pd
import altair as alt
import folium
from streamlit_folium import folium_static
import plotly.express as px
import plotly.graph_objects as go
# Import geopandas, zipfile, tempfile y os para el nuevo enfoque
import geopandas as gpd
import zipfile
import tempfile
import os
import io

# Título de la aplicación
st.set_page_config(layout="wide")
st.title('☔ Visor de Información Geoespacial de Precipitación 🌧️')
st.markdown("---")

# --- Sección para la carga de datos ---
with st.expander("📂 Cargar Datos"):
    st.write("Carga tu archivo `mapaCV.csv` y los archivos del shapefile (`.shp`, `.shx`, `.dbf`) comprimidos en un único archivo `.zip`.")
    
    # Carga de archivos CSV
    uploaded_file_csv = st.file_uploader("Cargar archivo .csv (mapaCV.csv)", type="csv")
    df = None
    if uploaded_file_csv:
        try:
            # Leer el archivo subido usando punto y coma como delimitador
            df = pd.read_csv(uploaded_file_csv, sep=';')
            st.success("Archivo CSV cargado exitosamente.")
        except Exception as e:
            st.error(f"Error al leer el archivo CSV: {e}")
            df = None
    else:
        try:
            # Intentar leer el archivo local con el delimitador ';'
            df = pd.read_csv('mapaCV.csv', sep=';')
            st.warning("Se ha cargado el archivo CSV usando ';' como separador.")
        except (FileNotFoundError, pd.errors.ParserError):
            st.warning("No se pudo leer 'mapaCV.csv'. Por favor, cárgalo manualmente o revisa su formato.")
            df = None

    # Carga de archivo Shapefile en formato ZIP
    uploaded_zip = st.file_uploader("Cargar shapefile (.zip)", type="zip")
    gdf = None
    if uploaded_zip:
        try:
            # Crea un directorio temporal para extraer los archivos
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extrae el contenido del archivo zip
                with zipfile.ZipFile(uploaded_zip, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # Encuentra el archivo .shp en el directorio extraído
                shp_files = [f for f in os.listdir(temp_dir) if f.endswith('.shp')]
                if shp_files:
                    shp_path = os.path.join(temp_dir, shp_files[0])
                    # Usa geopandas para leer el shapefile, que es más robusto
                    gdf = gpd.read_file(shp_path)
                    
                    # --- NUEVA CORRECCIÓN CLAVE ---
                    # Si el GeoDataFrame no tiene un CRS, se lo asignamos.
                    # Asumimos que es EPSG:4326 para que la transformación funcione.
                    if gdf.crs is None:
                        gdf.set_crs("EPSG:4326", inplace=True)
                    
                    # Ahora, convierte el GeoDataFrame a EPSG:4326 para que Folium lo pueda usar
                    gdf = gdf.to_crs("EPSG:4326")
                    
                    st.success("Archivos Shapefile cargados exitosamente y sistema de coordenadas configurado y convertido a WGS84.")
                else:
                    st.error("No se encontró ningún archivo .shp en el archivo ZIP. Asegúrate de que el archivo .zip contenga al menos un .shp.")
                    gdf = None
        except Exception as e:
            st.error(f"Error al procesar el archivo ZIP: {e}")

if df is not None:
    # Validar que las columnas necesarias existan
    required_cols = ['Nom_Est', 'Latitud', 'Longitud']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        st.error(f"Error: Las siguientes columnas requeridas no se encuentran en el archivo CSV: {', '.join(missing_cols)}. Por favor, verifica los nombres de las columnas en tu archivo.")
    else:
        # Convertir columnas a tipo numérico, manejando errores de 'nan'
        df['Latitud'] = pd.to_numeric(df['Latitud'], errors='coerce')
        df['Longitud'] = pd.to_numeric(df['Longitud'], errors='coerce')
        
        # Eliminar filas con valores NaN en latitud/longitud
        df.dropna(subset=['Latitud', 'Longitud'], inplace=True)
        
        # Verificar si el DataFrame está vacío después de la limpieza
        if df.empty:
            st.error("El DataFrame está vacío. Por favor, asegúrate de que tu archivo CSV contenga datos válidos en las columnas 'Nom_Est', 'Latitud' y 'Longitud'.")
        else:
            # --- Configuración de pestañas ---
            tab1, tab2, tab3, tab4 = st.tabs([
                "📊 Datos Tabulados", 
                "📈 Gráficos de Precipitación", 
                "🌎 Mapa de Estaciones", 
                "🎬 Animación de Lluvia"
            ])

            # --- Pestaña para opciones de filtrado ---
            st.sidebar.header("⚙️ Opciones de Filtrado")
            
            # Selección de estaciones
            all_stations = df['Nom_Est'].unique()
            
            # Opciones para seleccionar todas o ninguna
            col1, col2 = st.sidebar.columns(2)
            with col1:
                select_all = st.checkbox("Seleccionar todas", value=False)
            with col2:
                clear_all = st.checkbox("Eliminar selección", value=False)
            
            selected_stations_list = []
            if select_all:
                selected_stations_list = all_stations
            elif clear_all:
                selected_stations_list = []
            else:
                selected_stations_list = st.sidebar.multiselect(
                    "Elige las estaciones:",
                    options=all_stations,
                    default=[]
                )

            selected_stations_df = df[df['Nom_Est'].isin(selected_stations_list)]

            # Deslizadores para años
            start_year, end_year = st.sidebar.slider(
                "Elige el rango de años:",
                min_value=1970,
                max_value=2021,
                value=(1970, 2021)
            )
            
            years_to_analyze = [str(year) for year in range(start_year, end_year + 1)]

            # --- Pestaña para datos tabulados ---
            with tab1:
                st.header("📊 Datos Tabulados de las Estaciones")
                st.markdown("---")
                
                if selected_stations_df.empty:
                    st.info("Por favor, selecciona al menos una estación en la barra lateral.")
                else:
                    st.subheader("Información Adicional de las Estaciones Seleccionadas")
                    
                    # Columnas adicionales del CSV
                    info_cols = ['Nom_Est', 'porc_datos', 'departamento', 'municipio', 'vereda']
                    
                    # Filtra las columnas de años
                    year_cols_filtered = [str(year) for year in range(start_year, end_year + 1)]
                    
                    # Asegura que las columnas existan antes de seleccionarlas
                    cols_to_display = [col for col in info_cols + year_cols_filtered if col in df.columns]

                    st.dataframe(selected_stations_df[cols_to_display].set_index('Nom_Est'))

            # --- Pestaña para gráficos ---
            with tab2:
                st.header("📈 Gráficos de Precipitación")
                st.markdown("---")
                
                if selected_stations_df.empty:
                    st.info("Por favor, selecciona al menos una estación en la barra lateral.")
                else:
                    # Gráfico de línea/barra
                    st.subheader("Precipitación Anual por Estación")
                    chart_type = st.radio("Elige el tipo de gráfico:", ('Líneas', 'Barras'))
                    
                    # Prepara los datos para graficar
                    df_melted = selected_stations_df.melt(
                        id_vars=['Nom_Est'],
                        value_vars=years_to_analyze,
                        var_name='Año',
                        value_name='Precipitación'
                    )
                    df_melted['Año'] = df_melted['Año'].astype(int)

                    if chart_type == 'Líneas':
                        chart = alt.Chart(df_melted).mark_line(point=True).encode(
                            x=alt.X('Año:O', title='Año', axis=alt.Axis(format='d')),
                            y=alt.Y('Precipitación:Q', title='Precipitación (mm)'),
                            color=alt.Color('Nom_Est', title='Estación'),
                            tooltip=['Nom_Est', 'Año', 'Precipitación']
                        ).interactive()
                    else: # Barras
                        chart = alt.Chart(df_melted).mark_bar().encode(
                            x=alt.X('Año:O', title='Año', axis=alt.Axis(format='d')),
                            y=alt.Y('Precipitación:Q', title='Precipitación (mm)'),
                            color=alt.Color('Nom_Est', title='Estación'),
                            tooltip=['Nom_Est', 'Año', 'Precipitación']
                        ).interactive()
                    
                    st.altair_chart(chart, use_container_width=True)

                    # Gráfico de comparación de estaciones
                    st.subheader("Comparación de Precipitación entre Estaciones")
                    compare_year = st.selectbox(
                        "Selecciona el año para comparar:", 
                        options=years_to_analyze
                    )
                    
                    sort_order = st.radio("Ordenar por:", ('Mayor a menor', 'Menor a mayor'))
                    
                    # Prepara los datos para la comparación
                    df_compare = selected_stations_df[['Nom_Est', compare_year]].copy()
                    df_compare = df_compare.rename(columns={compare_year: 'Precipitación'})
                    
                    # Ordenar los datos
                    if sort_order == 'Mayor a menor':
                        df_compare = df_compare.sort_values(by='Precipitación', ascending=False)
                    else:
                        df_compare = df_compare.sort_values(by='Precipitación', ascending=True)

                    fig_bar = px.bar(
                        df_compare,
                        x='Nom_Est',
                        y='Precipitación',
                        title=f'Precipitación en el año {compare_year}',
                        labels={'Nom_Est': 'Estación', 'Precipitación': 'Precipitación (mm)'}
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)

            # --- Pestaña para el mapa ---
            with tab3:
                st.header("🌎 Mapa de Ubicación de las Estaciones")
                st.markdown("---")
                
                if gdf is None:
                    st.info("Por favor, carga el archivo shapefile en formato .zip en la sección 'Cargar Datos'.")
                elif selected_stations_df.empty:
                    st.info("Por favor, selecciona al menos una estación en la barra lateral.")
                else:
                    # Filtra el GeoDataFrame para incluir solo las estaciones seleccionadas
                    gdf_selected = gdf[gdf['Nom_Est'].isin(selected_stations_list)]
                    
                    if gdf_selected.empty:
                        st.info("Ninguna de las estaciones seleccionadas tiene información geoespacial en el shapefile.")
                    else:
                        # Se ha movido el cálculo del centro del mapa para evitar errores
                        map_center = [gdf_selected.geometry.centroid.y.mean(), gdf_selected.geometry.centroid.x.mean()]
                        m = folium.Map(location=map_center, zoom_start=8, tiles="CartoDB positron")
                        
                        # Agrega el GeoDataFrame al mapa de folium
                        folium.GeoJson(
                            gdf_selected,
                            name="Estaciones de Precipitación",
                            tooltip=folium.features.GeoJsonTooltip(fields=['Nom_Est'])
                        ).add_to(m)

                        folium_static(m)

            # --- Pestaña para animaciones ---
            with tab4:
                st.header("🎬 Animación de Precipitación Anual")
                st.markdown("---")
                
                if selected_stations_df.empty:
                    st.info("Por favor, selecciona al menos una estación en la barra lateral.")
                else:
                    animation_type = st.radio("Selecciona el tipo de animación:", ('Barras Animadas', 'Mapa Animado'))

                    if animation_type == 'Barras Animadas':
                        df_melted_anim = selected_stations_df.melt(
                            id_vars=['Nom_Est'],
                            value_vars=years_to_analyze,
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
                            labels={'Nom_Est': 'Estación', 'Precipitación': 'Precipitación (mm)'}
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else: # Mapa Animado
                        df_melted_map = selected_stations_df.melt(
                            id_vars=['Nom_Est', 'Latitud', 'Longitud'],
                            value_vars=years_to_analyze,
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
                            mapbox_style="carto-positron",
                            zoom=7,
                            title="Precipitación Anual Animada en el Mapa"
                        )
                        fig.update_layout(
                            mapbox_style="open-street-map",
                            mapbox_zoom=7,
                            mapbox_center={"lat": df_melted_map['Latitud'].mean(), "lon": df_melted_map['Longitud'].mean()},
                        )
                        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
                        st.plotly_chart(fig, use_container_width=True)
