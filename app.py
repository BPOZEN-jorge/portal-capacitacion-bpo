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
# BASE DE DATOS (PERSISTENCIA Y ESTADOS)
# ==========================================
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Tabla de ingresos de usuarios
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
        
        # Tabla de estado de módulos (Bloqueado/Desbloqueado)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS modulos_estado (
                modulo_id INTEGER PRIMARY KEY,
                activo INTEGER NOT NULL
            )
            """
        )
        
        # Insertar estados iniciales por defecto (todos activos = 1) si no existen
        for m_id in range(1, 5):
            cursor.execute(
                "INSERT OR IGNORE INTO modulos_estado (modulo_id, activo) VALUES (?, 1)",
                (m_id,)
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
            "SELECT id AS 'ID', nombre AS 'Nombre', canal AS 'Canal', fecha_hora AS 'Fecha / Hora' FROM ingresos ORDER BY id DESC",
            conn,
        )
    return df

def eliminar_ingreso_por_id(ingreso_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ingresos WHERE id = ?", (ingreso_id,))
        conn.commit()

def vaciar_todo_el_historial():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ingresos")
        conn.commit()

def obtener_estado_modulos() -> dict:
    """Devuelve un diccionario {modulo_id: bool} indicando si está activo/desbloqueado."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT modulo_id, activo FROM modulos_estado")
        rows = cursor.fetchall()
        return {m_id: bool(activo) for m_id, activo in rows}

def cambiar_estado_modulo(modulo_id: int, activo: bool):
    """Actualiza si un módulo está bloqueado u abierto."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE modulos_estado SET activo = ? WHERE modulo_id = ?",
            (1 if activo else 0, modulo_id)
        )
        conn.commit()

init_db()

# ==========================================
# CARGA DE MÓDULOS DESDE ST.SECRETS
# ==========================================
def get_modulos_capacitacion():
    estados = obtener_estado_modulos()
    modulos = [
        {
            "id": 1,
            "titulo": "Generador de Códigos QR",
            "descripcion": "Aprende a estructurar, personalizar y generar códigos QR interactivos de forma dinámica con nuestra guía.",
            "url": st.secrets["genially_urls"]["modulo_1"],
            "activo": estados.get(1, True)
        },
        {
            "id": 2,
            "titulo": "Inducción Corporativa BPO",
            "descripcion": "Explora la estructura general de la compañía, nuestros pilares operativos, misión y visión corporativa.",
            "url": st.secrets["genially_urls"]["modulo_2"],
            "activo": estados.get(2, True)
        },
        {
            "id": 3,
            "titulo": "Técnicas de Atención y Soporte",
            "descripcion": "Módulo enfocado en comunicación efectiva, resolución de incidencias complejas y empatía con el cliente.",
            "url": st.secrets["genially_urls"]["modulo_3"],
            "activo": estados.get(3, True)
        },
        {
            "id": 4,
            "titulo": "Seguridad de la Información",
            "descripcion": "Protocolos clave de ciberseguridad, manejo seguro de bases de datos y buenas prácticas informáticas.",
            "url": st.secrets["genially_urls"]["modulo_4"],
            "activo": estados.get(4, True)
        }
    ]
    return modulos

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
        
        todos_modulos = get_modulos_capacitacion()
        # Filtrar solo módulos activos/desbloqueados
        modulos_disponibles = [m for m in todos_modulos if m["activo"]]

        if not modulos_disponibles:
            st.warning("🔒 Actualmente todos los módulos de capacitación se encuentran temporalmente bloqueados por el administrador.")
        else:
            titulos_modulos = [f"{m['id']}. {m['titulo']}" for m in modulos_disponibles]
            modulo_elegido_titulo = st.selectbox("🎯 Selecciona un módulo para visualizar:", titulos_modulos)
            
            modulo_sel = next(m for m in modulos_disponibles if f"{m['id']}. {m['titulo']}" == modulo_elegido_titulo)

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

        tab1, tab2 = st.tabs(["📊 Registros de Ingreso", "🔒 Control y Bloqueo de Módulos"])

        # TAB 1: REGISTROS DE INGRESO
        with tab1:
            st.subheader("Historial de Asistencia y Control de Registros")
            
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

                st.markdown("---")
                st.subheader("⚙️ Gestión y Borrado de Registros")

                col_del_single, col_del_all = st.columns(2)

                with col_del_single:
                    st.write("🗑️ **Eliminar un registro específico:**")
                    id_a_eliminar = st.selectbox(
                        "Selecciona el ID a eliminar:",
                        options=df_ingresos["ID"].tolist()
                    )
                    if st.button("Eliminar Registro Seleccionado", type="primary"):
                        eliminar_ingreso_por_id(id_a_eliminar)
                        st.success(f"✅ Registro ID {id_a_eliminar} eliminado.")
                        st.rerun()

                with col_del_all:
                    st.write("⚠️ **Vaciar historial completo:**")
                    confirmar_vaciar = st.checkbox("Confirmo que deseo borrar TODOS los registros")
                    if st.button("Borrar TODO el Historial", disabled=not confirmar_vaciar):
                        vaciar_todo_el_historial()
                        st.success("✅ Se han eliminado todos los registros.")
                        st.rerun()

        # TAB 2: GESTIÓN Y BLOQUEO DE MÓDULOS
        with tab2:
            st.subheader("🔓 Gestor de Acceso a Módulos para Agentes")
            st.caption("Activa o desactiva la visibilidad de cada módulo. Los cambios se aplican de inmediato.")

            modulos = get_modulos_capacitacion()

            for m in modulos:
                col_info, col_toggle = st.columns([3, 1])
                
                with col_info:
                    st.markdown(f"**Módulo {m['id']}: {m['titulo']}**")
                    st.caption(m['descripcion'])
                
                with col_toggle:
                    # Switch interactivo
                    estado_actual = m['activo']
                    nuevo_estado = st.toggle(
                        "Desbloqueado" if estado_actual else "Bloqueado",
                        value=estado_actual,
                        key=f"toggle_mod_{m['id']}"
                    )
                    
                    # Si el estado cambió, actualizar DB
                    if nuevo_estado != estado_actual:
                        cambiar_estado_modulo(m['id'], nuevo_estado)
                        st.toast(f"Módulo {m['id']} {'desbloqueado' if nuevo_estado else 'bloqueado'}.")
                        st.rerun()
                
                st.markdown("---")