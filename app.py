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

# --- Sección de carga de datos ---
st.header("📂 Cargar Datos")
st.write("Carga tu archivo `.csv` y los archivos del shapefile (`.shp`, `.shx`, `.dbf`) comprimidos en un único archivo `.zip`.")

uploaded_file_csv = st.file_uploader("Cargar archivo .csv (mapaCV.csv)", type="csv")
uploaded_zip = st.file_uploader("Cargar shapefile (.zip)", type="zip")

df_csv = None
gdf = None
df = None

# --- Proceso de unión y preparación de datos ---
if uploaded_file_csv and uploaded_zip:
    try:
        # Carga del archivo CSV
        try:
            df_csv = pd.read_csv(uploaded_file_csv, sep=';', encoding='utf-8')
        except UnicodeDecodeError:
            df_csv = pd.read_csv(uploaded_file_csv, sep=';', encoding='latin-1')

        st.success("Archivo CSV cargado exitosamente.")

        # Carga del archivo Shapefile en formato ZIP
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
                
                st.success("Archivos Shapefile cargados exitosamente.")
            else:
                st.error("No se encontró ningún archivo .shp en el archivo ZIP. Asegúrate de que el archivo .zip contenga al menos un .shp.")
                gdf = None
    except Exception as e:
        st.error(f"Error al procesar los archivos: {e}")

    # Función robusta para encontrar y estandarizar nombres de columna
    def standardize_columns(dataframe, col_mapping):
        df_cols = [c.lower() for c in dataframe.columns]
        found_cols = {}
        for std_name, possible_names in col_mapping.items():
            found_col_name = None
            for name in possible_names:
                if name.lower() in df_cols:
                    found_col_name = dataframe.columns[df_cols.index(name.lower())]
                    break
            if found_col_name:
                found_cols[std_name] = found_col_name
                if found_col_name != std_name:
                    dataframe.rename(columns={found_col_name: std_name}, inplace=True)
        return dataframe, found_cols

    if df_csv is not None and gdf is not None:
        try:
            # Mapeo de columnas para estandarización
            col_mapping_gdf = {
                'Nom_Est': ['Nom_Est', 'nom_est', 'NOMBRE_VER', 'nombre_ver'],
                'municipio': ['NOMB_MPIO', 'nombre_ver', 'Mpio'],
                'vereda': ['NOMBRE_VER', 'nombre_ver', 'vereda'],
                'celda': ['Celda_XY', 'celda']
            }
            col_mapping_csv = {
                'Nom_Est': ['Nom_Est', 'nom_est', 'estacion', 'nombre', 'nombre_ver'],
                'municipio': ['municipio', 'NOMB_MPIO', 'Mpio'],
                'vereda': ['vereda', 'NOMBRE_VER', 'nombre_ver'],
                'celda': ['Celda_XY', 'celda']
            }
            
            # Estandarizar columnas en ambos DataFrames
            gdf, found_cols_gdf = standardize_columns(gdf, col_mapping_gdf)
            df_csv, found_cols_csv = standardize_columns(df_csv, col_mapping_csv)
            
            # Verificar que la columna clave de unión exista en ambos
            station_col_gdf = found_cols_gdf.get('Nom_Est')
            station_col_csv = found_cols_csv.get('Nom_Est')

            if not station_col_gdf or not station_col_csv:
                st.error("Error: No se encontró una columna de 'estación' común en ambos archivos para realizar la unión. Por favor, asegúrate de que ambos archivos tengan una columna para el nombre o ID de la estación (ej. 'Nom_Est', 'estacion', 'nombre_ver').")
                df = None
            else:
                # Unir el GeoDataFrame con el DataFrame del CSV
                df = gdf.merge(df_csv, on='Nom_Est', how='left', suffixes=('_gdf', '_csv'))

                for col in ['municipio', 'vereda', 'celda']:
                    if col not in df.columns:
                        df[col] = pd.NA
                
                # Preparar las coordenadas del centroide
                df['Latitud'] = df.geometry.centroid.y
                df['Longitud'] = df.geometry.centroid.x
                
                # Convertir las columnas a tipo numérico, manejando errores de 'nan'
                df['Latitud'] = pd.to_numeric(df['Latitud'], errors='coerce')
                df['Longitud'] = pd.to_numeric(df['Longitud'], errors='coerce')
                
                df.dropna(subset=['Latitud', 'Longitud'], inplace=True)
        except Exception as e:
            st.error(f"Error en el proceso de unión de datos: {e}")
            df = None

# --- Resto de la aplicación, solo se ejecuta si el DataFrame no es nulo ---
if df is not None and not df.empty:
    # --- Configuración de pestañas ---
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Datos Tabulados", 
        "📈 Gráficos de Precipitación", 
        "🌎 Mapa de Estaciones", 
        "🎬 Animación de Lluvia"
    ])
    
    # --- Filtros en la barra lateral ---
    st.sidebar.header("⚙️ Opciones de Filtrado")
    
    # Selectores por municipio y celda, ahora multiseleccionables
    municipios = sorted(df['municipio'].dropna().unique()) if 'municipio' in df.columns else []
    selected_municipio = st.sidebar.multiselect("Elige uno o más municipios:", municipios)
    
    celdas = sorted(df['celda'].dropna().unique()) if 'celda' in df.columns else []
    selected_celda = st.sidebar.multiselect("Elige una o más celdas:", celdas)

    # Filtrar el DataFrame según la selección de municipio y celda
    filtered_df_by_loc = df.copy()
    if selected_municipio and 'municipio' in filtered_df_by_loc.columns:
        filtered_df_by_loc = filtered_df_by_loc[filtered_df_by_loc['municipio'].isin(selected_municipio)]
    if selected_celda and 'celda' in filtered_df_by_loc.columns:
        filtered_df_by_loc = filtered_df_by_loc[filtered_df_by_loc['celda'].isin(selected_celda)]
    
    # Selección de estaciones, ordenadas alfabéticamente
    all_stations = sorted(filtered_df_by_loc['Nom_Est'].dropna().unique())
    
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
    years_to_analyze_present = [year for year in years_to_analyze if year in selected_stations_df.columns]
    
    # --- Pestaña para datos tabulados ---
    with tab1:
        st.header("📊 Datos Tabulados de las Estaciones")
        st.markdown("---")
        
        if selected_stations_df.empty:
            st.info("Por favor, selecciona al menos una estación en la barra lateral.")
        else:
            st.subheader("Información básica de las Estaciones Seleccionadas")
            
            info_cols = ['Nom_Est', 'estacion', 'municipio', 'vereda', 'celda']
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
            
            stats_cols = ['Nom_Est']
            if 'municipio' in selected_stations_df.columns:
                stats_cols.append('municipio')
            if 'vereda' in selected_stations_df.columns:
                stats_cols.append('vereda')
            stats_df = selected_stations_df[stats_cols].copy()
            
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
        elif not years_to_analyze_present:
            st.info("El rango de años seleccionado no contiene datos de precipitación para las estaciones seleccionadas. Por favor, ajusta el rango de años.")
        else:
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
                if not df_melted_temp.empty:
                    min_precip = df_melted_temp['Precipitación'].min()
                    max_precip = df_melted_temp['Precipitación'].max()
                    
                    min_y = st.number_input("Valor mínimo del eje Y:", value=float(min_precip), format="%.2f")
                    max_y = st.number_input("Valor máximo del eje Y:", value=float(max_precip), format="%.2f")
                    if min_y >= max_y:
                        st.warning("El valor mínimo debe ser menor que el valor máximo.")
                    else:
                        y_range = (min_y, max_y)
                else:
                    st.warning("No hay datos de precipitación para el rango de años y estaciones seleccionadas.")

            st.subheader("Precipitación Anual por Estación")
            chart_type = st.radio("Elige el tipo de gráfico:", ('Líneas', 'Barras'))
            
            df_melted = selected_stations_df.melt(
                id_vars=['Nom_Est'],
                value_vars=years_to_analyze_present,
                var_name='Año',
                value_name='Precipitación'
            )
            df_melted['Año'] = df_melted['Año'].astype(int)

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

    # --- Pestaña para el mapa ---
    with tab3:
        st.header("🌎 Mapa de Ubicación de las Estaciones")
        st.markdown("---")
        
        if gdf is None or gdf.empty:
            st.info("Por favor, carga el archivo shapefile en formato .zip en la sección 'Cargar Datos'.")
        elif selected_stations_df.empty:
            st.info("Por favor, selecciona al menos una estación en la barra lateral.")
        else:
            st.write("El mapa se ajusta automáticamente para mostrar todas las estaciones seleccionadas. Puedes usar los botones de abajo para centrar la vista.")

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
                if st.button("Centrar en Estaciones Seleccionadas"):
                    st.session_state.center_on_stations = True
                    st.session_state.reset_map_colombia = False
                    st.session_state.reset_map_antioquia = False

            map_center = [4.5709, -74.2973]
            zoom_level = 6

            if 'reset_map_colombia' in st.session_state and st.session_state.reset_map_colombia:
                st.session_state.reset_map_colombia = False
            elif 'reset_map_antioquia' in st.session_state and st.session_state.reset_map_antioquia:
                map_center = [6.2442, -75.5812]
                zoom_level = 8
                st.session_state.reset_map_antioquia = False
            elif 'center_on_stations' in st.session_state and st.session_state.center_on_stations:
                gdf_selected = df[df['Nom_Est'].isin(selected_stations_list)]
                if not gdf_selected.empty:
                    map_center = [gdf_selected.geometry.centroid.y.mean(), gdf_selected.geometry.centroid.x.mean()]
                    zoom_level = 8
                st.session_state.center_on_stations = False
            else:
                gdf_selected = df[df['Nom_Est'].isin(selected_stations_list)]
                if not gdf_selected.empty:
                    map_center = [gdf_selected.geometry.centroid.y.mean(), gdf_selected.geometry.centroid.x.mean()]
                    zoom_level = 8

            m = folium.Map(location=map_center, zoom_start=zoom_level, tiles="CartoDB positron")

            gdf_selected_for_bounds = df[df['Nom_Est'].isin(selected_stations_list)]
            if not gdf_selected_for_bounds.empty:
                bounds = [[gdf_selected_for_bounds.total_bounds[1], gdf_selected_for_bounds.total_bounds[0]], 
                          [gdf_selected_for_bounds.total_bounds[3], gdf_selected_for_bounds.total_bounds[2]]]
                m.fit_bounds(bounds)

            if not df.empty:
                gdf_final = df.copy()
                stats_df_cols = ['Nom_Est']
                if 'municipio' in gdf_final.columns:
                    stats_df_cols.append('municipio')
                if 'vereda' in gdf_final.columns:
                    stats_df_cols.append('vereda')
                
                stats_df = selected_stations_df[stats_df_cols].copy()
                if years_to_analyze_present:
                    stats_df['Precipitación Media (mm)'] = selected_stations_df[years_to_analyze_present].mean(axis=1).round(2)
                
                gdf_final = gdf_final.merge(stats_df, on='Nom_Est', how='left', suffixes=('', '_stat'))
                
                tooltip_fields = ['Nom_Est', 'municipio', 'vereda', 'Precipitación Media (mm)']
                tooltip_aliases = ['Estación', 'Municipio', 'Vereda', 'Precipitación Media']
                
                existing_fields = [f for f in tooltip_fields if f in gdf_final.columns]
                existing_aliases = [tooltip_aliases[i] for i, f in enumerate(tooltip_fields) if f in gdf_final.columns]
                
                folium.GeoJson(
                    gdf_final.to_json(),
                    name='Áreas del Shapefile',
                    tooltip=folium.features.GeoJsonTooltip(fields=existing_fields,
                                                            aliases=existing_aliases,
                                                            style=("background-color: white; color: #333333; font-family: sans-serif; font-size: 12px; padding: 10px;"))
                ).add_to(m)

                for idx, row in gdf_final.iterrows():
                    if pd.notna(row['Latitud']) and pd.notna(row['Longitud']):
                        precip_media = row.get('Precipitación Media (mm)', 'N/A')
                        if isinstance(precip_media, (int, float)):
                            precip_str = f"{precip_media:.2f}"
                        else:
                            precip_str = str(precip_media)

                        pop_up_text = (
                            f"<b>Estación:</b> {row['Nom_Est']}<br>"
                            f"<b>Municipio:</b> {row.get('municipio', 'N/A')}<br>"
                            f"<b>Vereda:</b> {row.get('vereda', 'N/A')}<br>"
                            f"<b>Precipitación Media:</b> {precip_str} mm"
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
        elif not years_to_analyze_present:
            st.info("El rango de años seleccionado no contiene datos de precipitación para las estaciones seleccionadas. Por favor, ajusta el rango de años.")
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
