import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# ==========================================
# CONFIGURACIÓN DE PÁGINA
# ==========================================
st.set_page_config(
    page_title="Portal de Capacitación BPO",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_PATH = "registros_ingresos.db"

# ==========================================
# BASE DE DATOS (PERSISTENCIA DE INGRESOS)
# ==========================================
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ingresos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                canal TEXT NOT NULL,
                fecha_hora DATETIME NOT NULL
            )
            """
        )
        conn.commit()

def registrar_ingreso(nombre: str, canal: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO ingresos (nombre, canal, fecha_hora) VALUES (?, ?, ?)",
            (nombre.strip(), canal, now),
        )
        conn.commit()

def obtener_historial_ingresos() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            "SELECT id, nombre AS 'Nombre', canal AS 'Canal', fecha_hora AS 'Fecha / Hora' FROM ingresos ORDER BY id DESC",
            conn,
        )
    return df

init_db()

# ==========================================
# CARGA DE MÓDULOS DESDE ST.SECRETS
# ==========================================
def get_modulos_capacitacion():
    return [
        {
            "id": 1,
            "titulo": "Generador de Códigos QR",
            "descripcion": "Aprende a estructurar, personalizar y generar códigos QR interactivos de forma dinámica con nuestra guía.",
            "url": st.secrets["genially_urls"]["modulo_1"]
        },
        {
            "id": 2,
            "titulo": "Inducción Corporativa BPO",
            "descripcion": "Explora la estructura general de la compañía, nuestros pilares operativos, misión y visión corporativa.",
            "url": st.secrets["genially_urls"]["modulo_2"]
        },
        {
            "id": 3,
            "titulo": "Técnicas de Atención y Soporte",
            "descripcion": "Módulo enfocado en comunicación efectiva, resolución de incidencias complejas y empatía con el cliente.",
            "url": st.secrets["genially_urls"]["modulo_3"]
        },
        {
            "id": 4,
            "titulo": "Seguridad de la Información",
            "descripcion": "Protocolos clave de ciberseguridad, manejo seguro de bases de datos y buenas prácticas informáticas.",
            "url": st.secrets["genially_urls"]["modulo_4"]
        }
    ]

# ==========================================
# GESTIÓN DE SESIÓN
# ==========================================
if "user_authenticated" not in st.session_state:
    st.session_state.user_authenticated = False
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False
if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = {}

# ==========================================
# INTERFAZ Y NAVEGACIÓN
# ==========================================
st.sidebar.title("📌 Portal Capacitación")
rol_seleccionado = st.sidebar.radio(
    "Selecciona la vista:",
    ["Vista Usuario / Agente", "Vista Administrador"]
)

# ------------------------------------------
# VISTA 1: USUARIO / AGENTE
# ------------------------------------------
if rol_seleccionado == "Vista Usuario / Agente":
    st.title("🎓 Módulos de Capacitación Interactiva")

    if not st.session_state.user_authenticated:
        st.subheader("🔐 Autenticación de Usuario")
        
        with st.form("form_login_usuario"):
            password_input = st.text_input("Contraseña de Usuario:", type="password")
            nombre_input = st.text_input("Tu Nombre Completo:", placeholder="Ej: Maria Lopez")
            canal_input = st.selectbox("Selecciona tu Canal:", ["ATC", "Cobros", "Ventas"])
            
            submit_user = st.form_submit_button("Ingresar y Registrar Asistencia", use_container_width=True)

        if submit_user:
            if not password_input or not nombre_input.strip():
                st.error("⚠️ Por favor completa tu nombre y la contraseña.")
            elif password_input != st.secrets["passwords"]["user_password"]:
                st.error("❌ Contraseña de usuario incorrecta.")
            else:
                registrar_ingreso(nombre_input, canal_input)
                st.session_state.user_authenticated = True
                st.session_state.usuario_actual = {
                    "nombre": nombre_input.strip(),
                    "canal": canal_input
                }
                st.success(f"✅ ¡Bienvenido/a {nombre_input}! Asistencia registrada en canal **{canal_input}**.")
                st.rerun()

    else:
        user = st.session_state.usuario_actual
        st.sidebar.markdown("---")
        st.sidebar.success(f"👤 **Usuario:** {user.get('nombre')}\n\n📡 **Canal:** {user.get('canal')}")
        
        if st.sidebar.button("Cerrar Sesión", use_container_width=True):
            st.session_state.user_authenticated = False
            st.session_state.usuario_actual = {}
            st.rerun()

        st.subheader(f"Módulos asignados para el canal: **{user.get('canal')}**")
        
        modulos = get_modulos_capacitacion()
        titulos_modulos = [f"{m['id']}. {m['titulo']}" for m in modulos]
        modulo_elegido_titulo = st.selectbox("🎯 Selecciona un módulo para visualizar:", titulos_modulos)
        
        modulo_sel = next(m for m in modulos if f"{m['id']}. {m['titulo']}" == modulo_elegido_titulo)

        st.markdown(f"### {modulo_sel['titulo']}")
        st.info(modulo_sel['descripcion'])
        st.markdown("---")
        components.iframe(modulo_sel['url'], height=600, scrolling=True)

# ------------------------------------------
# VISTA 2: ADMINISTRADOR
# ------------------------------------------
elif rol_seleccionado == "Vista Administrador":
    st.title("🛡️ Panel de Administración")

    if not st.session_state.admin_authenticated:
        st.subheader("🔑 Acceso Restringido - Administrador")
        
        with st.form("form_login_admin"):
            admin_pass_input = st.text_input("Contraseña Administrador:", type="password")
            submit_admin = st.form_submit_button("Ingresar al Panel Admin", use_container_width=True)

        if submit_admin:
            if admin_pass_input == st.secrets["passwords"]["admin_password"]:
                st.session_state.admin_authenticated = True
                st.success("✅ Acceso concedido como Administrador.")
                st.rerun()
            else:
                st.error("❌ Contraseña de administrador incorrecta.")

    else:
        if st.sidebar.button("Cerrar Sesión Admin", use_container_width=True):
            st.session_state.admin_authenticated = False
            st.rerun()

        tab1, tab2 = st.tabs(["📊 Registros de Ingreso / Asistencia", "📚 Vista Previa de Módulos"])

        # TAB 1: REGISTROS DE INGRESO
        with tab1:
            st.subheader("Historial de Usuarios que marcaron ingreso")
            
            df_ingresos = obtener_historial_ingresos()
            
            if df_ingresos.empty:
                st.info("Aún no hay registros de ingreso en el sistema.")
            else:
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Ingresos", len(df_ingresos))
                col2.metric("Canales Activos", df_ingresos["Canal"].nunique())
                col3.metric("Último Ingreso", df_ingresos["Fecha / Hora"].iloc[0])

                st.markdown("---")
                
                canal_filtro = st.multiselect(
                    "Filtrar por Canal:",
                    options=list(df_ingresos["Canal"].unique()),
                    default=list(df_ingresos["Canal"].unique())
                )
                
                df_filtrado = df_ingresos[df_ingresos["Canal"].isin(canal_filtro)]
                st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

                csv_data = df_filtrado.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Descargar Reporte CSV",
                    data=csv_data,
                    file_name=f"reporte_ingresos_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                )

        # TAB 2: VISTA PREVIA DE MÓDULOS
        with tab2:
            st.subheader("Auditoría de Contenido y Previsualización")
            modulos = get_modulos_capacitacion()

            for m in modulos:
                with st.expander(f"📌 Módulo {m['id']}: {m['titulo']}"):
                    st.write(f"**Descripción:** {m['descripcion']}")
                    components.iframe(m['url'], height=450, scrolling=True)