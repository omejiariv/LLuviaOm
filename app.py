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
            df = pd.read_csv(uploaded_file_csv, sep=';')
            # Renombrar columnas con los nombres correctos del usuario
            df = df.rename(columns={'Mpio': 'municipio', 'NOMBRE_VER': 'vereda'})
            st.success("Archivo CSV cargado exitosamente.")
        except Exception as e:
            st.error(f"Error al leer el archivo CSV: {e}")
            df = None
    else:
        try:
            df = pd.read_csv('mapaCV.csv', sep=';')
            # Renombrar columnas con los nombres correctos del usuario
            df = df.rename(columns={'Mpio': 'municipio', 'NOMBRE_VER': 'vereda'})
            st.warning("Se ha cargado el archivo CSV usando ';' como separador.")
        except (FileNotFoundError, pd.errors.ParserError):
            st.warning("No se pudo leer 'mapaCV.csv'. Por favor, cárgalo manualmente o revisa su formato.")
            df = None

    # Carga de archivo Shapefile en formato ZIP
    uploaded_zip = st.file_uploader("Cargar shapefile (.zip)", type="zip")
    gdf = None
    if uploaded_zip:
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                with zipfile.ZipFile(uploaded_zip, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                shp_files = [f for f in os.listdir(temp_dir) if f.endswith('.shp')]
                if shp_files:
                    shp_path = os.path.join(temp_dir, shp_files[0])
                    gdf = gpd.read_file(shp_path)
                    
                    # Asignar el CRS correcto y convertir a WGS84
                    # MAGNA-SIRGAS_CMT12 corresponde a EPSG:9377
                    gdf.set_crs("EPSG:9377", inplace=True)
                    gdf = gdf.to_crs("EPSG:4326")
                    
                    st.success("Archivos Shapefile cargados exitosamente y sistema de coordenadas configurado y convertido a WGS84.")
                else:
                    st.error("No se encontró ningún archivo .shp en el archivo ZIP. Asegúrate de que el archivo .zip contenga al menos un .shp.")
                    gdf = None
        except Exception as e:
            st.error(f"Error al procesar el archivo ZIP: {e}")

if df is not None:
    # Validar que las columnas necesarias existan
    required_cols = ['Nom_Est', 'Latitud', 'Longitud', 'municipio', 'Celda_XY', 'vereda', 'estacion', 'departamento']
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
            
            # Selectores por municipio y celda
            municipios = sorted(df['municipio'].unique())
            selected_municipio = st.sidebar.selectbox("Elige un municipio:", ['Todos'] + municipios)
            
            celdas = sorted(df['Celda_XY'].unique())
            selected_celda = st.sidebar.selectbox("Elige una celda:", ['Todas'] + celdas)

            # Filtrar el DataFrame según la selección de municipio y celda
            filtered_df_by_loc = df.copy()
            if selected_municipio != 'Todos':
                filtered_df_by_loc = filtered_df_by_loc[filtered_df_by_loc['municipio'] == selected_municipio]
            if selected_celda != 'Todas':
                filtered_df_by_loc = filtered_df_by_loc[filtered_df_by_loc['Celda_XY'] == selected_celda]
            
            # Selección de estaciones, ordenadas alfabéticamente
            all_stations = sorted(filtered_df_by_loc['Nom_Est'].unique())
            
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
            
            # Asegura que las columnas de años existan en el DataFrame antes de usarlas
            years_to_analyze_present = [year for year in years_to_analyze if year in selected_stations_df.columns]
            
            # --- Pestaña para datos tabulados ---
            with tab1:
                st.header("📊 Datos Tabulados de las Estaciones")
                st.markdown("---")
                
                if selected_stations_df.empty:
                    st.info("Por favor, selecciona al menos una estación en la barra lateral.")
                else:
                    st.subheader("Información básica de las Estaciones Seleccionadas")
                    
                    # Columnas adicionales del CSV
                    info_cols = ['Nom_Est', 'estacion', 'porc_datos', 'departamento', 'municipio', 'vereda', 'Celda_XY']
                    
                    cols_to_display = [col for col in info_cols + years_to_analyze_present if col in df.columns]

                    # Aplicar escala de colores a los datos de precipitación
                    styled_df = selected_stations_df[cols_to_display].set_index('Nom_Est').style.background_gradient(cmap='RdYlBu_r', subset=years_to_analyze_present)
                    st.dataframe(styled_df)

                    # Nueva tabla con estadísticas
                    st.subheader("Estadísticas de Precipitación")
                    
                    # Prepara el DataFrame para estadísticas
                    stats_df = selected_stations_df[['Nom_Est', 'estacion', 'municipio', 'vereda']].copy()
                    
                    if years_to_analyze_present:
                        # Calcular max, min, mean, std
                        stats_df['Precipitación Máxima (mm)'] = selected_stations_df[years_to_analyze_present].max(axis=1)
                        stats_df['Año Máximo'] = selected_stations_df[years_to_analyze_present].idxmax(axis=1)
                        stats_df['Precipitación Mínima (mm)'] = selected_stations_df[years_to_analyze_present].min(axis=1)
                        stats_df['Año Mínimo'] = selected_stations_df[years_to_analyze_present].idxmin(axis=1)
                        stats_df['Precipitación Media (mm)'] = selected_stations_df[years_to_analyze_present].mean(axis=1).round(2)
                        stats_df['Desviación Estándar'] = selected_stations_df[years_to_analyze_present].std(axis=1).round(2)

                        # Agregar una fila de resumen para todas las estaciones
                        summary_row = pd.DataFrame([{
                            'Nom_Est': 'Todas las estaciones',
                            'estacion': '',
                            'municipio': '',
                            'vereda': '',
                            'Precipitación Máxima (mm)': selected_stations_df[years_to_analyze_present].max().max(),
                            'Año Máximo': selected_stations_df[years_to_analyze_present].idxmax().max(),
                            'Precipitación Mínima (mm)': selected_stations_df[years_to_analyze_present].min().min(),
                            'Año Mínimo': selected_stations_df[years_to_analyze_present].idxmin().min(),
                            'Precipitación Media (mm)': selected_stations_df[years_to_analyze_present].mean().mean().round(2),
                            'Desviación Estándar': selected_stations_df[years_to_analyze_present].std().mean().round(2)
                        }])
                        stats_df = pd.concat([stats_df, summary_row], ignore_index=True)

                    st.dataframe(stats_df.set_index('Nom_Est'))

            # --- Pestaña para gráficos ---
            with tab2:
                st.header("📈 Gráficos de Precipitación")
                st.markdown("---")
                
                if selected_stations_df.empty:
                    st.info("Por favor, selecciona al menos una estación en la barra lateral.")
                else:
                    st.subheader("Precipitación Anual por Estación")
                    chart_type = st.radio("Elige el tipo de gráfico:", ('Líneas', 'Barras'))
                    
                    df_melted = selected_stations_df.melt(
                        id_vars=['Nom_Est'],
                        value_vars=years_to_analyze_present,
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
                    else:
                        chart = alt.Chart(df_melted).mark_bar().encode(
                            x=alt.X('Año:O', title='Año', axis=alt.Axis(format='d')),
                            y=alt.Y('Precipitación:Q', title='Precipitación (mm)'),
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
                    gdf_selected = gdf[gdf['Nom_Est'].isin(selected_stations_list)]
                    
                    gdf_selected = gdf_selected.merge(stats_df, on='Nom_Est', how='left')

                    if gdf_selected.empty:
                        st.info("Ninguna de las estaciones seleccionadas tiene información geoespacial en el shapefile.")
                    else:
                        # Crear el mapa de Folium
                        map_center = [gdf_selected.geometry.centroid.y.mean(), gdf_selected.geometry.centroid.x.mean()]
                        m = folium.Map(location=map_center, zoom_start=8, tiles="CartoDB positron")
                        
                        # Añadir las áreas (polígonos) del shapefile al mapa
                        folium.GeoJson(
                            gdf_selected.to_json(),
                            name='Áreas del Shapefile',
                            tooltip=folium.features.GeoJsonTooltip(fields=['Nom_Est', 'municipio', 'vereda', 'Precipitación Media (mm)'],
                                                                    aliases=['Estación', 'Municipio', 'Vereda', 'Precipitación Media'],
                                                                    style=("background-color: white; color: #333333; font-family: sans-serif; font-size: 12px; padding: 10px;"))
                        ).add_to(m)

                        # Añadir los marcadores circulares para las estaciones
                        for idx, row in gdf_selected.iterrows():
                            if pd.notna(row['Latitud']) and pd.notna(row['Longitud']):
                                pop_up_text = (
                                    f"<b>Estación:</b> {row['Nom_Est']}<br>"
                                    f"<b>Municipio:</b> {row['municipio']}<br>"
                                    f"<b>Vereda:</b> {row['vereda']}<br>"
                                    f"<b>Precipitación Media:</b> {row['Precipitación Media (mm)']:.2f} mm"
                                )
                                tooltip_text = f"Estación: {row['Nom_Est']}"

                                icon_size = 12

                                folium.CircleMarker(
                                    location=[row['Latitud'], row['Longitud']],
                                    radius=icon_size / 2,
                                    popup=pop_up_text,
                                    tooltip=tooltip_text,
                                    color='blue',
                                    fill=True,
                                    fill_color='blue',
                                    fill_opacity=0.6
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
                            labels={'Nom_Est': 'Estación', 'Precipitación': 'Precipitación (mm)'}
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
