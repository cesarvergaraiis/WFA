import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# 1. Configuración de la página
st.set_page_config(page_title="Dashboard WFA - Gantt", layout="wide")

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
    
    # Normalizar correos
    df_wfa['mail'] = df_wfa['mail'].astype(str).str.strip().str.lower()
    df_lists['mail'] = df_lists['mail'].astype(str).str.strip().str.lower()
    
    # Cruce de datos
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
    # Formato: "04 May - 29 May"
    df_combined['Rango_Texto'] = (
        df_combined['FECHA Beneficio'].dt.strftime('%d %b') + 
        " - " + 
        df_combined['Fecha Fin'].dt.strftime('%d %b')
    )
    
    return df_combined.dropna(subset=['FECHA Beneficio', 'Fecha Fin', 'NOMBRE'])

try:
    df = load_and_process_data()

    # 3. Barra Lateral - Filtros
    st.sidebar.header("Filtros")

    teams = sorted(df['Team'].dropna().unique())
    selected_teams = st.sidebar.multiselect("Equipos", options=teams, default=teams)

    locations = sorted(df['Location'].dropna().unique())
    selected_locations = st.sidebar.multiselect("Países", options=locations, default=locations)

    st.sidebar.markdown("---")
    st.sidebar.subheader("Accesos Rápidos de Fecha")
    
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

    # 4. Aplicar Filtros
    if len(date_selection) == 2:
        mask = (
            df['Team'].isin(selected_teams) & 
            df['Location'].isin(selected_locations) &
            (df['FECHA Beneficio'].dt.date <= date_selection[1]) & 
            (df['Fecha Fin'].dt.date >= date_selection[0])
        )
        df_filtered = df[mask].sort_values(by='FECHA Beneficio')
    else:
        df_filtered = pd.DataFrame()

    # 5. Gráfico Gantt con Texto Interno
    if not df_filtered.empty:
        st.subheader("Cronograma WFA")
        
#        df_filtered['Fecha_Fin_Visual'] = df['Fecha fin'] + pd.Timedelta(days=1)
        
        # Agregamos el parámetro 'text' usando la columna de rango
        fig = px.timeline(
            df_filtered, 
            x_start="FECHA Beneficio", 
            x_end="Fecha Fin", 
            y="NOMBRE", 
            color="Team",
            text="Rango_Texto", # <--- Texto dentro de la barra
            hover_data=["Location", "NOTA"],
            template="plotly_white",
            labels={"NOMBRE": "Colaborador", "Team": "Equipo"}
        )
        
        # Configurar posición y estilo del texto
        fig.update_traces(
            textposition='inside', 
            insidetextanchor='middle',
            textfont_size=10
        )
        
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(height=max(400, len(df_filtered)*35), xaxis_title="Calendario")
        
        # Línea de hoy
        fig.add_vline(x=datetime.now().timestamp() * 1000, line_dash="dash", line_color="red", annotation_text="Hoy")

        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df_filtered[['NOMBRE', 'Team', 'Location', 'FECHA Beneficio', 'Fecha Fin', 'NOTA']], use_container_width=True)
    else:
        st.warning("No hay datos para el rango seleccionado.")

except Exception as e:
    st.error(f"Error: {e}")