import streamlit as st
import pandas as pd
import altair as alt
import folium
from streamlit_folium import folium_static
import plotly.express as px
import plotly.graph_objects as go
import shapefile
import io

# Título de la aplicación
st.title('☔ Visor de Información Geoespacial de Precipitación 🌧️')

# --- Sección para la carga de datos ---
## Carga de Datos
with st.expander("📂 Cargar Datos"):
    st.write("Carga tu archivo `mapasCV.csv` y los archivos del shapefile (`.shp`, `.shx`, `.dbf`).")
    
    # Carga de archivos CSV
    uploaded_file_csv = st.file_uploader("Cargar archivo .csv (mapasCV.csv)", type="csv")
    if uploaded_file_csv:
        df = pd.read_csv(uploaded_file_csv)
    else:
        try:
            df = pd.read_csv('mapasCV.csv')
        except FileNotFoundError:
            st.warning("No se encontró el archivo 'mapasCV.csv'. Por favor, cárgalo manualmente.")
            df = None

    # Carga de archivos Shapefile
    uploaded_shp = st.file_uploader("Cargar archivo .shp", type="shp")
    uploaded_shx = st.file_uploader("Cargar archivo .shx", type="shx")
    uploaded_dbf = st.file_uploader("Cargar archivo .dbf", type="dbf")

    sf = None
    if uploaded_shp and uploaded_shx and uploaded_dbf:
        shp_data = uploaded_shp.getvalue()
        shx_data = uploaded_shx.getvalue()
        dbf_data = uploaded_dbf.getvalue()
        try:
            sf = shapefile.Reader(shp=io.BytesIO(shp_data), shx=io.BytesIO(shx_data), dbf=io.BytesIO(dbf_data))
        except Exception as e:
            st.error(f"Error al leer los archivos shapefile: {e}")
    else:
        try:
            sf = shapefile.Reader('mapasCV.shp')
        except FileNotFoundError:
            st.warning("No se encontraron los archivos shapefile. Por favor, cárgalos manualmente.")
            sf = None

if df is not None:
    # --- Configuración de pestañas ---
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Datos Tabulados", 
        "📈 Gráficos de Precipitación", 
        "🌎 Mapa de Estaciones", 
        "🎬 Animación de Lluvia", 
        "⚙️ Opciones de Filtrado"
    ])

    # --- Pestaña para opciones de filtrado (al inicio para mejor UX) ---
    with tab5:
        st.header("⚙️ Opciones de Filtrado y Selección")
        st.markdown("---")
        
        # Selección de estaciones
        all_stations = df['Nom_Est'].unique()
        
        # Opción para seleccionar todas las estaciones o ninguna
        select_all = st.checkbox("Seleccionar todas las estaciones", value=False)
        clear_all = st.checkbox("Eliminar selección", value=False)
        
        selected_stations_list = []
        if select_all:
            selected_stations_list = all_stations
        elif clear_all:
            selected_stations_list = []
        else:
            selected_stations_list = st.multiselect(
                "Elige las estaciones para el análisis:",
                options=all_stations,
                default=[]
            )

        selected_stations_df = df[df['Nom_Est'].isin(selected_stations_list)]

        # Deslizadores para años
        all_years = [str(year) for year in range(1970, 2022)]
        start_year, end_year = st.slider(
            "Elige el rango de años para el análisis:",
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
            st.info("Por favor, selecciona al menos una estación en la pestaña 'Opciones de Filtrado'.")
        else:
            st.subheader("Información Adicional de las Estaciones Seleccionadas")
            
            # Columnas adicionales del CSV
            info_cols = ['Nom_Est', 'porc_datos', 'departamento', 'municipio', 'vereda']
            
            # Filtra las columnas de años
            year_cols_filtered = [str(year) for year in range(start_year, end_year + 1)]
            
            # Asegura que las columnas existan antes de seleccionarlas
            cols_to_display = [col for col in info_cols + year_cols_filtered if col in df.columns]

            st.dataframe(selected_stations_df[cols_to_display])

    # --- Pestaña para gráficos ---
    with tab2:
        st.header("📈 Gráficos de Precipitación")
        st.markdown("---")
        
        if selected_stations_df.empty:
            st.info("Por favor, selecciona al menos una estación en la pestaña 'Opciones de Filtrado'.")
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
        
        if sf is None:
            st.info("Por favor, carga los archivos del shapefile en la sección 'Cargar Datos'.")
        elif selected_stations_df.empty:
            st.info("Por favor, selecciona al menos una estación en la pestaña 'Opciones de Filtrado'.")
        else:
            # Crear un mapa base con Folium
            map_center = [selected_stations_df['Latitud'].mean(), selected_stations_df['Longitud'].mean()]
            m = folium.Map(location=map_center, zoom_start=8, tiles="CartoDB positron")
            
            # Cargar y añadir las estaciones del shapefile
            for shape in sf.shapes():
                for point in shape.points:
                    lon, lat = point[0], point[1]
                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=5,
                        color='blue',
                        fill=True,
                        fill_color='blue',
                        tooltip=f"Estación: {df[df['Longitud'] == lon]['Nom_Est'].iloc[0]}"
                    ).add_to(m)

            folium_static(m)

    # --- Pestaña para animaciones ---
    with tab4:
        st.header("🎬 Animación de Precipitación Anual")
        st.markdown("---")
        
        if selected_stations_df.empty:
            st.info("Por favor, selecciona al menos una estación en la pestaña 'Opciones de Filtrado'.")
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