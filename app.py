import sqlite3
import uuid
import ipaddress
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# ==========================================
# CONFIGURACIÓN DE PÁGINA Y ZONA HORARIA
# ==========================================
st.set_page_config(
    page_title="Portal de Capacitación BPO",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_PATH = "registros_ingresos.db"

# ==========================================
# CONFIGURACIÓN DE IPS / REDES PERMITIDAS
# ==========================================
IPS_O_RANGOS_PERMITIDOS = [
    "186.97.167.230",      # IP pública exacta de Tigo
    "186.97.167.0/24",     # Subred pública de Tigo (186.97.167.1 - 186.97.167.254)
    "10.0.0.0/8",          # Redes privadas e infraestructura interna/proxy (incluye 10.12.73.x)
    "172.16.0.0/12",       # Contenedores / Proxies de Docker o Servidor
    "192.168.0.0/16",      # Redes LAN privadas
    "127.0.0.1"            # Localhost
]

def obtener_hora_colombia() -> str:
    """Devuelve la fecha y hora actual en zona horaria de Colombia (America/Bogota)."""
    return datetime.now(ZoneInfo("America/Bogota")).strftime("%Y-%m-%d %H:%M:%S")

def obtener_ip_cliente() -> str:
    """Obtiene la dirección IP remota del cliente leyendo los encabezados HTTP."""
    try:
        headers = st.context.headers
        if "X-Forwarded-For" in headers:
            return headers["X-Forwarded-For"].split(",")[0].strip()
        elif "X-Real-Ip" in headers:
            return headers["X-Real-Ip"].strip()
    except Exception:
        pass
    return "127.0.0.1"

def validar_ip_tigo() -> bool:
    """Verifica si la IP del usuario coincide con la lista de IPs o rangos autorizados."""
    ip_usuario = obtener_ip_cliente()
    try:
        ip_obj = ipaddress.ip_address(ip_usuario)
        for red_o_ip in IPS_O_RANGOS_PERMITIDOS:
            red_obj = ipaddress.ip_network(red_o_ip, strict=False)
            if ip_obj in red_obj:
                return True
    except ValueError:
        return False
    return False

# Generar un ID único para la sesión del navegador actual si no existe
if "session_token" not in st.session_state:
    st.session_state.session_token = str(uuid.uuid4())

# ==========================================
# BASE DE DATOS (PERSISTENCIA Y ESTADOS)
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
        
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS modulos_estado (
                modulo_id INTEGER PRIMARY KEY,
                activo INTEGER NOT NULL
            )
            """
        )
        
        cursor.execute("PRAGMA table_info(solicitudes_acceso)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if columns and ("session_token" not in columns or "ip" not in columns):
            cursor.execute("DROP TABLE solicitudes_acceso")
        
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS solicitudes_acceso (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                canal TEXT NOT NULL,
                session_token TEXT NOT NULL,
                ip TEXT DEFAULT 'Desconocida',
                modulo_id INTEGER NOT NULL,
                estado TEXT NOT NULL,
                fecha_solicitud DATETIME NOT NULL,
                UNIQUE(session_token, modulo_id)
            )
            """
        )
        
        cursor.execute(
            "INSERT OR IGNORE INTO modulos_estado (modulo_id, activo) VALUES (?, 0)",
            (1,)
        )
            
        conn.commit()

def registrar_ingreso(nombre: str, canal: str):
    now = obtener_hora_colombia()
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
            "SELECT id AS 'ID', nombre AS 'Nombre', canal AS 'Canal', fecha_hora AS 'Fecha / Hora (COL)' FROM ingresos ORDER BY id DESC",
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
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT modulo_id, activo FROM modulos_estado")
        rows = cursor.fetchall()
        return {m_id: bool(activo) for m_id, activo in rows}

def cambiar_estado_modulo(modulo_id: int, activo: bool):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE modulos_estado SET activo = ? WHERE modulo_id = ?",
            (1 if activo else 0, modulo_id)
        )
        conn.commit()

def solicitar_acceso_modulo(nombre: str, canal: str, session_token: str, ip: str, modulo_id: int):
    now = obtener_hora_colombia()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO solicitudes_acceso (nombre, canal, session_token, ip, modulo_id, estado, fecha_solicitud)
            VALUES (?, ?, ?, ?, ?, 'PENDIENTE', ?)
            """,
            (nombre.strip(), canal, session_token, ip, modulo_id, now)
        )
        conn.commit()

def obtener_estado_solicitud(session_token: str, modulo_id: int) -> str:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT estado FROM solicitudes_acceso WHERE session_token = ? AND modulo_id = ?",
            (session_token, modulo_id)
        )
        row = cursor.fetchone()
        return row[0] if row else "NO_SOLICITADO"

def obtener_todas_solicitudes() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            "SELECT id, nombre, canal, session_token, ip, modulo_id, estado, fecha_solicitud FROM solicitudes_acceso ORDER BY id DESC",
            conn
        )
    return df

def actualizar_estado_solicitud(solicitud_id: int, nuevo_estado: str):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE solicitudes_acceso SET estado = ? WHERE id = ?",
            (nuevo_estado, solicitud_id)
        )
        conn.commit()

def eliminar_solicitud(solicitud_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM solicitudes_acceso WHERE id = ?", (solicitud_id,))
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
            "titulo": "BPO General",
            "descripcion": "Módulo general de inducción y capacitación BPO.",
            "url": st.secrets["genially_urls"]["modulo_1"],
            "activo_global": estados.get(1, False)
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
# VERIFICACIÓN RIGUROSA DE IP (CORTAFUEGOS)
# ==========================================
ip_detectada = obtener_ip_cliente()

if not validar_ip_tigo():
    st.error("🚫 **ACCESO NO AUTORIZADO**")
    st.warning(
        f"No puedes ingresar a este portal desde tu red actual.\n\n"
        f"**IP detectada:** `{ip_detectada}`\n\n"
        f"Por razones de seguridad, la plataforma solo está disponible desde la red corporativa autorizada."
    )
    st.stop()

# ==========================================
# INTERFAZ Y NAVEGACIÓN (Solo accesible si la IP es válida)
# ==========================================
st.sidebar.title("📌 Portal Capacitación")
st.sidebar.caption(f"🌐 IP Autorizada: `{ip_detectada}`")

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
            canal_input = st.selectbox("Selecciona tu Canal:", ["ATC", "Cobros", "Ventas", "Administrativos"])
            
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
        
        col_hdr1, col_hdr2 = st.columns([3, 1])
        with col_hdr2:
            if st.button("🔄 Comprobar Autorización", use_container_width=True):
                st.rerun()

        if st.sidebar.button("Cerrar Sesión", use_container_width=True):
            st.session_state.user_authenticated = False
            st.session_state.usuario_actual = {}
            st.rerun()

        st.subheader(f"Módulos asignados para el canal: **{user.get('canal')}**")
        
        modulos = get_modulos_capacitacion()
        
        for m in modulos:
            st.markdown(f"### Módulo {m['id']}: {m['titulo']}")
            st.info(m['descripcion'])
            
            estado_solicitud = obtener_estado_solicitud(st.session_state.session_token, m['id'])
            desbloqueado_para_usuario = m['activo_global'] or (estado_solicitud == "APROBADO")
            
            if desbloqueado_para_usuario:
                st.success("🔓 Acceso Autorizado para esta sesión.")
                components.iframe(m['url'], height=600, scrolling=True)
            else:
                if estado_solicitud == "PENDIENTE":
                    st.warning("⏳ **Solicitud Pendiente de Aprobación.** Tu solicitud ha sido enviada al administrador desde este dispositivo.")
                    if st.button("🔄 Verificar si ya fue Aprobado", key=f"check_perm_{m['id']}", type="secondary"):
                        st.rerun()
                else:
                    st.warning("🔒 Este módulo requiere autorización previa del administrador para este dispositivo.")
                    if st.button("📩 Solicitar Acceso al Administrador", type="primary", key=f"btn_sol_{m['id']}"):
                        solicitar_acceso_modulo(user['nombre'], user['canal'], st.session_state.session_token, ip_detectada, m['id'])
                        st.success("✅ Solicitud enviada correctamente al Administrador.")
                        st.rerun()
            st.markdown("---")

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

        tab1, tab2 = st.tabs(["📊 Registros de Ingreso", "🔒 Control y Solicitudes de Módulos"])

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
                col3.metric("Último Ingreso (COL)", df_ingresos["Fecha / Hora (COL)"].iloc[0])

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
                    file_name=f"reporte_ingresos_{datetime.now(ZoneInfo('America/Bogota')).strftime('%Y%m%d_%H%M')}.csv",
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

        # TAB 2: GESTIÓN DE AUTORIZACIONES Y SOLICITUDES DE MÓDULOS
        with tab2:
            col_admin_title, col_admin_refresh = st.columns([3, 1])
            with col_admin_title:
                st.subheader("📩 Solicitudes de Acceso de Usuarios")
            with col_admin_refresh:
                if st.button("🔄 Actualizar Solicitudes", use_container_width=True, type="primary"):
                    st.toast("Listado de solicitudes actualizado.")
                    st.rerun()

            st.caption("Aprueba las solicitudes de acceso o elimínalas si deseas rechazar la petición.")

            df_solicitudes = obtener_todas_solicitudes()

            if df_solicitudes.empty:
                st.info("No hay solicitudes registradas por el momento.")
            else:
                for idx, sol in df_solicitudes.iterrows():
                    col_user, col_status, col_btn1, col_btn2 = st.columns([3, 2, 1.5, 1.5])
                    
                    with col_user:
                        ip_registrada = sol.get('ip', '127.0.0.1')
                        st.markdown(f"👤 **{sol['nombre']}** ({sol['canal']})")
                        st.caption(f"Módulo ID: {sol['modulo_id']} | IP: `{ip_registrada}` | Dispositivo: `{sol['session_token'][:8]}...` | Fecha (COL): {sol['fecha_solicitud']}")
                    
                    with col_status:
                        if sol['estado'] == 'PENDIENTE':
                            st.warning("⏳ Pendiente")
                        elif sol['estado'] == 'APROBADO':
                            st.success("✅ Aprobado")

                    with col_btn1:
                        if sol['estado'] != 'APROBADO':
                            if st.button("Aprobar Acceso", key=f"app_{sol['id']}", type="primary"):
                                actualizar_estado_solicitud(sol['id'], "APROBADO")
                                st.toast(f"Acceso APROBADO para {sol['nombre']}")
                                st.rerun()
                        else:
                            st.write("✓ Ya Aprobado")

                    with col_btn2:
                        if st.button("Rechazar / Eliminar", key=f"rej_{sol['id']}"):
                            eliminar_solicitud(sol['id'])
                            st.toast(f"Solicitud ELIMINADA para {sol['nombre']}")
                            st.rerun()

                    st.markdown("---")

            st.subheader("🔓 Control Global de Módulos (Todos los Usuarios)")
            st.caption("Si activas el switch global, el módulo estará disponible para TODOS los dispositivos sin necesidad de solicitar aprobación.")
            
            modulos = get_modulos_capacitacion()
            for m in modulos:
                col_info, col_toggle = st.columns([3, 1])
                with col_info:
                    st.markdown(f"**Módulo {m['id']}: {m['titulo']}**")
                with col_toggle:
                    estado_actual = m['activo_global']
                    nuevo_estado = st.toggle(
                        "Desbloqueo Global",
                        value=estado_actual,
                        key=f"toggle_mod_{m['id']}"
                    )
                    if nuevo_estado != estado_actual:
                        cambiar_estado_modulo(m['id'], nuevo_estado)
                        st.toast(f"Módulo {m['id']} {'desbloqueado para todos' if nuevo_estado else 'bloqueado globalmente'}.")
                        st.rerun()
