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
        except (FileNotFound, pd.errors.ParserError):
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
            
            # Selectores por municipio y celda, ahora multiseleccionables
            municipios = sorted(df['municipio'].unique())
            selected_municipio = st.sidebar.multiselect("Elige uno o más municipios:", municipios)
            
            celdas = sorted(df['Celda_XY'].unique())
            selected_celda = st.sidebar.multiselect("Elige una o más celdas:", celdas)

            # Filtrar el DataFrame según la selección de municipio y celda
            filtered_df_by_loc = df.copy()
            if selected_municipio:
                filtered_df_by_loc = filtered_df_by_loc[filtered_df_by_loc['municipio'].isin(selected_municipio)]
            if selected_celda:
                filtered_df_by_loc = filtered_df_by_loc[filtered_df_by_loc['Celda_XY'].isin(selected_celda)]
            
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
                    df_to_display = selected_stations_df[cols_to_display].set_index('Nom_Est')

                    # Aplicar escala de colores a los datos de precipitación
                    if not df_to_display.empty and years_to_analyze_present:
                        try:
                            styled_df = df_to_display.style.background_gradient(cmap='RdYlBu_r', subset=years_to_analyze_present)
                            st.dataframe(styled_df)
                        except Exception as e:
                            st.error(f"Error al aplicar estilo de tabla: {e}. Mostrando tabla sin estilo.")
                            st.dataframe(df_to_display)
                    else:
                        st.dataframe(df_to_display)

                    # Nueva tabla con estadísticas
                    st.subheader("Estadísticas de Precipitación")
                    
                    # Prepara el DataFrame para estadísticas
                    stats_df = selected_stations_df[['Nom_Est', 'estacion', 'municipio', 'vereda']].copy()
                    
                    if years_to_analyze_present and not selected_stations_df.empty:
                        # Calcular max, min, mean, std
                        stats_df['Precipitación Máxima (mm)'] = selected_stations_df[years_to_analyze_present].max(axis=1).round(2)
                        stats_df['Año Máximo'] = selected_stations_df[years_to_analyze_present].idxmax(axis=1)
                        stats_df['Precipitación Mínima (mm)'] = selected_stations_df[years_to_analyze_present].min(axis=1).round(2)
                        stats_df['Año Mínimo'] = selected_stations_df[years_to_analyze_present].idxmin(axis=1)
                        stats_df['Precipitación Media (mm)'] = selected_stations_df[years_to_analyze_present].mean(axis=1).round(2)
                        stats_df['Desviación Estándar'] = selected_stations_df[years_to_analyze_present].std(axis=1).round(2)

                        # Agregar una fila de resumen para todas las estaciones
                        df_melted_stats = selected_stations_df.melt(
                            id_vars=['Nom_Est'],
                            value_vars=years_to_analyze_present,
                            var_name='Año',
                            value_name='Precipitación'
                        )
                        
                        if not df_melted_stats.empty:
                            max_precip = df_melted_stats['Precipitación'].max()
                            min_precip = df_melted_stats['Precipitación'].min()
                            
                            try:
                                max_year = df_melted_stats[df_melted_stats['Precipitación'] == max_precip]['Año'].iloc[0]
                            except IndexError:
                                max_year = 'N/A'
                            
                            try:
                                min_year = df_melted_stats[df_melted_stats['Precipitación'] == min_precip]['Año'].iloc[0]
                            except IndexError:
                                min_year = 'N/A'
                            
                            summary_row = pd.DataFrame([{
                                'Nom_Est': 'Todas las estaciones',
                                'estacion': '',
                                'municipio': '',
                                'vereda': '',
                                'Precipitación Máxima (mm)': max_precip,
                                'Año Máximo': max_year,
                                'Precipitación Mínima (mm)': min_precip,
                                'Año Mínimo': min_year,
                                'Precipitación Media (mm)': df_melted_stats['Precipitación'].mean().round(2),
                                'Desviación Estándar': df_melted_stats['Precipitación'].std().round(2)
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
                    # Controles para el eje vertical
                    st.subheader("Opciones de Eje Vertical (Y)")
                    axis_control = st.radio("Elige el control del eje Y:", ('Automático', 'Personalizado'))
                    y_range = None
                    if axis_control == 'Personalizado':
                        df_melted_temp = selected_stations_df.melt(
                            id_vars=['Nom_Est'],
                            value_vars=years_to_analyze_present,
                            var_name='Año',
                            value_name='Precipitación'
                        )
                        min_precip = df_melted_temp['Precipitación'].min()
                        max_precip = df_melted_temp['Precipitación'].max()
                        
                        min_y = st.number_input("Valor mínimo del eje Y:", value=float(min_precip), format="%.2f")
                        max_y = st.number_input("Valor máximo del eje Y:", value=float(max_precip), format="%.2f")
                        if min_y >= max_y:
                            st.warning("El valor mínimo debe ser menor que el valor máximo.")
                        else:
                            y_range = (min_y, max_y)

                    st.subheader("Precipitación Anual por Estación")
                    chart_type = st.radio("Elige el tipo de gráfico:", ('Líneas', 'Barras'))
                    
                    df_melted = selected_stations_df.melt(
                        id_vars=['Nom_Est'],
                        value_vars=years_to_analyze_present,
                        var_name='Año',
                        value_name='Precipitación'
                    )
                    df_melted['Año'] = df_melted['Año'].astype(int)

                    # Aplicar el rango del eje Y si es personalizado
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

                    # Aplicar el rango del eje Y al gráfico de barras de Plotly
                    fig_bar = px.bar(
                        df_compare,
                        x='Nom_Est',
                        y='Precipitación',
                        title=f'Precipitación en el año {compare_year}',
                        labels={'Nom_Est': 'Estación', 'Precipitación': 'Precipitación (mm)'},
                        range_y=y_range
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
                    st.write("El mapa se ajusta automáticamente para mostrar todas las estaciones seleccionadas. Si el mapa parece muy alejado, es porque las estaciones están muy distantes entre sí. Puedes usar los botones de abajo para centrar la vista.")

                    # Botones para centrar el mapa
                    col_map1, col_map2, col_map3 = st.columns(3)
                    with col_map1:
                        if st.button("Centrar en Colombia"):
                            st.session_state.reset_map_colombia = True
                            st.session_state.reset_map_antioquia = False
                            st.session_state.center_on_stations = False
                    with col_map2:
                        if st.button("Centrar en Antioquia"):
                            st.session_state.reset_map_antioquia = True
                            st.session_state.reset_map_colombia = False
                            st.session_state.center_on_stations = False
                    with col_map3:
                        # Nuevo botón para centrar en las estaciones seleccionadas
                        if st.button("Centrar en Estaciones Seleccionadas"):
                            st.session_state.center_on_stations = True
                            st.session_state.reset_map_colombia = False
                            st.session_state.reset_map_antioquia = False

                    # Crear el mapa de Folium
                    if 'reset_map_colombia' in st.session_state and st.session_state.reset_map_colombia:
                        map_center = [4.5709, -74.2973] # Centro de Colombia
                        m = folium.Map(location=map_center, zoom_start=6, tiles="CartoDB positron")
                        st.session_state.reset_map_colombia = False
                    elif 'reset_map_antioquia' in st.session_state and st.session_state.reset_map_antioquia:
                        # Coordenadas aproximadas del centro de Antioquia
                        map_center = [6.2442, -75.5812]
                        m = folium.Map(location=map_center, zoom_start=8, tiles="CartoDB positron")
                        st.session_state.reset_map_antioquia = False
                    elif 'center_on_stations' in st.session_state and st.session_state.center_on_stations:
                        gdf_selected = gdf[gdf['Nom_Est'].isin(selected_stations_list)]
                        if not gdf_selected.empty:
                            map_center = [gdf_selected.geometry.centroid.y.mean(), gdf_selected.geometry.centroid.x.mean()]
                            m = folium.Map(location=map_center, zoom_start=8, tiles="CartoDB positron")
                            bounds = [[gdf_selected.total_bounds[1], gdf_selected.total_bounds[0]], 
                                      [gdf_selected.total_bounds[3], gdf_selected.total_bounds[2]]]
                            m.fit_bounds(bounds)
                        else:
                            map_center = [4.5709, -74.2973] # Fallback to Colombia
                            m = folium.Map(location=map_center, zoom_start=6, tiles="CartoDB positron")
                        st.session_state.center_on_stations = False
                    else:
                        gdf_selected = gdf[gdf['Nom_Est'].isin(selected_stations_list)]
                        
                        if not gdf_selected.empty:
                            map_center = [gdf_selected.geometry.centroid.y.mean(), gdf_selected.geometry.centroid.x.mean()]
                            m = folium.Map(location=map_center, zoom_start=8, tiles="CartoDB positron")
                            
                            # Ajustar el encuadre del mapa a las estaciones seleccionadas
                            bounds = [[gdf_selected.total_bounds[1], gdf_selected.total_bounds[0]], 
                                      [gdf_selected.total_bounds[3], gdf_selected.total_bounds[2]]]
                            m.fit_bounds(bounds)
                        else:
                            map_center = [4.5709, -74.2973]
                            m = folium.Map(location=map_center, zoom_start=6, tiles="CartoDB positron")
                    
                    gdf_selected = gdf[gdf['Nom_Est'].isin(selected_stations_list)]
                    gdf_selected = gdf_selected.merge(stats_df, on='Nom_Est', how='left')

                    if not gdf_selected.empty:
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
                        if years_to_analyze_present:
                            df_melted_anim = selected_stations_df.melt(
                                id_vars=['Nom_Est'],
                                value_vars=years_to_analyze_present,
                                var_name='Año',
                                value_name='Precipitación'
                            )
                            df_melted_anim['Año'] = df_melted_anim['Año'].astype(str)

                            # Aplicar el rango del eje Y si es personalizado a la animación de barras
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
                        else:
                            st.info("El rango de años seleccionado no contiene datos de precipitación para las estaciones seleccionadas. Por favor, ajusta el rango de años.")
                    else: # Mapa Animado
                        if years_to_analyze_present:
                            df_melted_map = selected_stations_df.melt(
                                id_vars=['Nom_Est', 'Latitud', 'Longitud'],
                                value_vars=years_to_analyze_present,
                                var_name='Año',
                                value_name='Precipitación'
                            )
                            
                            # Aplicar el rango de color del eje Y si es personalizado a la animación del mapa
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
                            fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("El rango de años seleccionado no contiene datos de precipitación para las estaciones seleccionadas. Por favor, ajusta el rango de años.")
