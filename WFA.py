import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# 1. Configuración de la página
st.set_page_config(page_title="WFA", layout="wide")
page_icon = "👥"
st.title("📊 SW Beneficio WFA")

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

    date_selection = st.sidebar.date_input("Rango manual", value=st.session_state.date_range)

    # 4. Creación de Pestañas Principales
    tab1, tab2 = st.tabs(["📅 Cronograma WFA", "📊 Cantidad WFA Solicitadas"])

    # --- PESTAÑA 1: CRONOGRAMA ---
    with tab1:
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
            # REPARACIÓN: Asegurar que no haya nulos y forzar enteros en ambas columnas clave
            df_lists_filtered['WFA tomados'] = pd.to_numeric(df_lists_filtered['WFA tomados'], errors='coerce').fillna(0).astype(int)
            df_lists_filtered['Límite WFA'] = pd.to_numeric(df_lists_filtered['Límite WFA'], errors='coerce').fillna(4).astype(int)

            columnas_render = ['mail', 'Team', 'Location', 'WFA tomados', 'Límite WFA']
            
            # REPARACIÓN: Extraer la lista de máximos con seguridad
            lista_maximos = df_lists_filtered['Límite WFA'].tolist()
            
            st.dataframe(
                df_lists_filtered[columnas_render],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "mail": st.column_config.TextColumn("Correo Electrónico"),
                    "Team": st.column_config.TextColumn("Equipo"),
                    "Location": st.column_config.TextColumn("País"),
                    "Límite WFA": st.column_config.NumberColumn("Límite Permitido", format="%d"),
                    "WFA tomados": st.column_config.ProgressColumn(
                        "WFA Tomados vs Límite",
                        help="Días consumidos sobre el total permitido por país (CL: 12, Otros: 4)",
                        format="%d",
                        min_value=0,
                        # Si por alguna razón la lista falla, por defecto cae en 12 para evitar el quiebre del Canvas
                        max_value=lista_maximos if lista_maximos else 12 
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

except Exception as e:
    st.error(f"Error general en la aplicación: {e}")