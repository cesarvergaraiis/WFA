import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# 1. Configuración de la página
st.set_page_config(page_title="WFA", layout="wide")

st.title("📊 SW Beneficio WFA")
page_icon = "👥"
# URL y GIDs confirmados
url = "https://docs.google.com/spreadsheets/d/1phPfVZrXO3reP4xoeltILvOIRmNMqhS4aQz4-601_Pk/edit"
gid_wfa = "0"
gid_lists = "1065399618"

# 2. Conexión
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=300)
def load_and_process_data():
    df_wfa = conn.read(spreadsheet=url, worksheet=gid_wfa)
    df_lists = conn.read(spreadsheet=url, worksheet=gid_lists)
    
    df_wfa.columns = df_wfa.columns.str.strip()
    df_lists.columns = df_lists.columns.str.strip()
    
    # Normalizar correos y textos clave
    df_wfa['mail'] = df_wfa['mail'].astype(str).str.strip().str.lower()
    df_lists['mail'] = df_lists['mail'].astype(str).str.strip().str.lower()
    df_lists['Location'] = df_lists['Location'].astype(str).str.strip().str.upper()
    df_lists['Team'] = df_lists['Team'].astype(str).str.strip()
    
    # Asegurar que WFA tomados sea numérico
    df_lists['WFA tomados'] = pd.to_numeric(df_lists['WFA tomados'], errors='coerce').fillna(0).astype(int)
    
    # Asignar límites según Location (CL: 12, Otros: 4)
    df_lists['Límite WFA'] = df_lists['Location'].apply(lambda x: 12 if x == 'CL' else 4)
    
    # Cruce de datos para el cronograma
    df_combined = pd.merge(
        df_wfa, 
        df_lists[['mail', 'Team', 'Location']].drop_duplicates(), 
        on='mail', 
        how='left'
    )
    
    # Procesamiento de fechas dd-mm-yyyy
    df_combined['FECHA Beneficio'] = pd.to_datetime(df_combined['FECHA Beneficio'], dayfirst=True, errors='coerce')
    df_combined['Fecha Fin'] = pd.to_datetime(df_combined['Fecha Fin'], dayfirst=True, errors='coerce')
    
    # Crear etiqueta de texto para las barras
    df_combined['Rango_Texto'] = (
        df_combined['FECHA Beneficio'].dt.strftime('%d %b') + 
        " - " + 
        df_combined['Fecha Fin'].dt.strftime('%d %b')
    )
    
    return df_combined, df_lists

try:
    df, df_lists_raw = load_and_process_data()

    # 3. Barra Lateral - Filtros Globales
    st.sidebar.header("Filtros Globales")

    # Obtener valores únicos combinando ambas fuentes para evitar pérdidas de datos
    all_teams = sorted(list(set(df['Team'].dropna().unique()).union(set(df_lists_raw['Team'].dropna().unique()))))
    selected_teams = st.sidebar.multiselect("Equipos", options=all_teams, default=all_teams)

    all_locations = sorted(list(set(df['Location'].dropna().unique()).union(set(df_lists_raw['Location'].dropna().unique()))))
    selected_locations = st.sidebar.multiselect("Países", options=all_locations, default=all_locations)

    st.sidebar.markdown("---")
    st.sidebar.subheader("Accesos Rápidos de Fecha (Cronograma)")
    
    today = datetime.now().date()
    
    if 'date_range' not in st.session_state:
        st.session_state.date_range = [df['FECHA Beneficio'].min().date(), df['Fecha Fin'].max().date()]

    col1, col2 = st.sidebar.columns(2)
    if col1.button("Hoy"):
        st.session_state.date_range = [today, today]
    if col2.button("Próx 30 días"):
        st.session_state.date_range = [today, today + timedelta(days=30)]
    if st.sidebar.button("Ver Todo"):
        st.session_state.date_range = [df['FECHA Beneficio'].min().date(), df['Fecha Fin'].max().date()]

    date_selection = st.sidebar.date_input("Rango manual", value=st.session_state.date_range, format="DD/MM/YYYY")

    # 4. Creación de Pestañas Principales (Se agrega la Pestaña 3)
    tab1, tab2, tab3 = st.tabs(["📅 Cronograma WFA", "📊 Cantidad WFA Solicitados", "👥 Sin Beneficio en Periodo"])

    # --- FILTRADO DE CRONOGRAMA (Se calcula arriba para usarlo en Tab 1 y Tab 3) ---
    if len(date_selection) == 2:
        mask = (
            df['Team'].isin(selected_teams) & 
            df['Location'].isin(selected_locations) &
            (df['FECHA Beneficio'].dt.date <= date_selection[1]) & 
            (df['Fecha Fin'].dt.date >= date_selection[0])
        )
        df_filtered = df[mask].dropna(subset=['FECHA Beneficio', 'Fecha Fin', 'NOMBRE']).sort_values(by='FECHA Beneficio')
    else:
        df_filtered = pd.DataFrame()

    # --- PESTAÑA 1: CRONOGRAMA ---
    with tab1:
        if not df_filtered.empty:
            st.subheader("Cronograma WFA Activos")
            
            df_filtered['Fecha_Fin_Visual'] = df_filtered['Fecha Fin'] + pd.Timedelta(days=1)
            
            fig = px.timeline(
                df_filtered, 
                x_start="FECHA Beneficio", 
                x_end="Fecha_Fin_Visual", 
                y="NOMBRE", 
                color="Team",
                text="Rango_Texto",
                hover_data=["Location", "NOTA"],
                template="plotly_white",
                labels={"NOMBRE": "Colaborador", "Team": "Equipo"}
            )
            
            fig.update_traces(
                textposition='inside', 
                insidetextanchor='middle',
                textfont_size=10
            )
            
            fig.update_yaxes(autorange="reversed")
            fig.update_layout(height=max(400, len(df_filtered)*35), xaxis_title="Calendario")
            fig.add_vline(x=datetime.now().timestamp() * 1000, line_dash="dash", line_color="red", annotation_text="Hoy")

            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df_filtered[['NOMBRE', 'Team', 'Location', 'FECHA Beneficio', 'Fecha Fin', 'NOTA']], use_container_width=True)
        else:
            st.warning("No hay datos de cronograma para los filtros seleccionados.")

    # --- PESTAÑA 2: CANTIDAD WFA SOLICITADAS ---
    with tab2:
        st.subheader("Control de Límites y WFA Consumidos")
        
        # Filtrar la lista base (gid=1065399618) por los filtros laterales
        mask_lists = df_lists_raw['Team'].isin(selected_teams) & df_lists_raw['Location'].isin(selected_locations)
        df_lists_filtered = df_lists_raw[mask_lists].copy()
        
        if not df_lists_filtered.empty:
            # Asegurar que no haya nulos y forzar enteros en ambas columnas clave
            df_lists_filtered['WFA tomados'] = pd.to_numeric(df_lists_filtered['WFA tomados'], errors='coerce').fillna(0).astype(int)
            df_lists_filtered['Límite WFA'] = pd.to_numeric(df_lists_filtered['Límite WFA'], errors='coerce').fillna(4).astype(int)

            # Calcular el porcentaje en formato decimal (ej: 0.45 para 45%)
            df_lists_filtered['% Consumido'] = (df_lists_filtered['WFA tomados'] / df_lists_filtered['Límite WFA']).fillna(0)
            
            # Formatear una columna de texto descriptivo
            df_lists_filtered['Progreso Real'] = (
                df_lists_filtered['WFA tomados'].astype(str) + " / " + df_lists_filtered['Límite WFA'].astype(str)
            )

            # Columnas organizadas para mostrar
            columnas_render = ['mail', 'Team', 'Location', 'Progreso Real', '% Consumido']
            
            # 1. Calculamos el valor máximo real de la columna para que la barra no se rompa si alguien se pasa del 100%
            max_value_progress = float(max(1.0, df_lists_filtered['% Consumido'].max()))

            st.dataframe(
                df_lists_filtered[columnas_render],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "mail": st.column_config.TextColumn("Correo Electrónico"),
                    "Team": st.column_config.TextColumn("Equipo"),
                    "Location": st.column_config.TextColumn("País"),
                    "Progreso Real": st.column_config.TextColumn("Días Tomados / Límite"),
                    "% Consumido": st.column_config.ProgressColumn(
                        "Uso del Beneficio",
                        help="Porcentaje consumido según el límite de su país (CL: 12 días, Otros: 4 días)",
                        format="%.0f",  # 👈 CAMBIO CLAVE: Quitamos el '%%' del final. Streamlit multiplicará el decimal por 100 y le pondrá el % automáticamente.
                        min_value=0.0,
                        max_value=max_value_progress  # 👈 CAMBIO CLAVE: Evita que valores mayores a 1.0 muestren siempre 1% o rompan la visualización
                    )
                }
            )
            
            # Métricas de resumen rápido
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Colaboradores Filtrados", len(df_lists_filtered))
            c2.metric("Total WFA Consumidos", df_lists_filtered['WFA tomados'].sum())
            
            # Alertas de usuarios en el límite
            en_limite = df_lists_filtered[df_lists_filtered['WFA tomados'] >= df_lists_filtered['Límite WFA']]
            if not en_limite.empty:
                st.error(f"⚠️ Hay {len(en_limite)} colaborador(es) que alcanzaron o superaron su límite permitido de WFA.")
        else:
            st.warning("No hay registros en la lista que coincidan con los filtros de Team y País seleccionados.")

    # --- NUEVA PESTAÑA 3: SIN BENEFICIO EN EL PERIODO ---
    with tab3:
        st.subheader("Personas sin WFA Activo en el Periodo Seleccionado")
        
        if len(date_selection) == 2:
            st.caption(f"Periodo evaluado: **{date_selection[0].strftime('%d/%m/%Y')}** al **{date_selection[1].strftime('%d/%m/%Y')}**")
            
            if not df_lists_filtered.empty:
                # Obtener lista de correos que SÍ tienen WFA en este rango de fechas
                correos_con_wfa = df_filtered['mail'].unique()
                
                # Filtrar la lista general para dejar solo a los que NO están en la lista anterior
                df_sin_wfa = df_lists_filtered[~df_lists_filtered['mail'].isin(correos_con_wfa)].copy()
                
                if not df_sin_wfa.empty:
                    st.info(f"👥 Hay **{len(df_sin_wfa)}** personas que no registran días de WFA en este rango de fechas.")
                    
                    # Mostrar tabla resumida
                    st.dataframe(
                        df_sin_wfa[['mail', 'Team', 'Location', 'WFA tomados', 'Límite WFA']],
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "mail": st.column_config.TextColumn("Correo Electrónico"),
                            "Team": st.column_config.TextColumn("Equipo"),
                            "Location": st.column_config.TextColumn("País"),
                            "WFA tomados": st.column_config.NumberColumn("Total Histórico Tomado"),
                            "Límite WFA": st.column_config.NumberColumn("Límite Permitido")
                        }
                    )
                else:
                    st.success("¡Todos los colaboradores filtrados tienen solicitudes de WFA registradas en este periodo!")
            else:
                st.warning("No hay colaboradores disponibles con los filtros de Equipo y País actuales.")
        else:
            st.warning("Por favor selecciona un rango de fechas válido en la barra lateral.")

except Exception as e:
    st.error(f"Error general en la aplicación: {e}")