import json
import time as time_lib
import uuid
import ipaddress
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from github import Github, GithubException
from streamlit_javascript import st_javascript

# ==========================================
# CONFIGURACIÓN DE PÁGINA Y ZONA HORARIA
# ==========================================
st.set_page_config(
    page_title="Portal de Capacitación BPO",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Archivo de persistencia JSON en GitHub
FILE_PORTAL_DATOS = "portal_capacitacion_datos.json"

def obtener_fecha_hora_colombia() -> datetime:
    """Retorna objeto datetime actual en Zona Horaria de Colombia."""
    return datetime.now(ZoneInfo("America/Bogota"))

def obtener_hora_colombia_str() -> str:
    """Retorna la fecha y hora actual formateada en hora de Colombia."""
    return obtener_fecha_hora_colombia().strftime("%Y-%m-%d %H:%M:%S")

# ==========================================
# CONEXIÓN Y OPERACIONES EN GITHUB (JSON)
# ==========================================
def obtener_repositorio_github():
    token = st.secrets.get("github", {}).get("token")
    repo_name = st.secrets.get("github", {}).get("repo")
    if not token or not repo_name:
        st.error("⚠️ Configuración incompleta de GitHub en los secretos (`st.secrets`).")
        st.stop()
    g = Github(token)
    return g.get_repo(repo_name)

def leer_json_github(file_path: str, default_payload: dict) -> dict:
    repo = obtener_repositorio_github()
    branch = st.secrets.get("github", {}).get("branch", "main")
    try:
        content = repo.get_contents(file_path, ref=branch)
        return json.loads(content.decoded_content.decode("utf-8"))
    except GithubException as e:
        if e.status == 404:
            escribir_json_github(file_path, default_payload, f"Inicializar {file_path}")
            return default_payload
        st.error(f"Error leyendo {file_path}: {e}")
        st.stop()

def escribir_json_github(file_path: str, payload: dict, mensaje_commit: str, retries: int = 3):
    repo = obtener_repositorio_github()
    branch = st.secrets.get("github", {}).get("branch", "main")
    json_str = json.dumps(payload, indent=4, ensure_ascii=False)

    for intento in range(retries):
        try:
            try:
                content = repo.get_contents(file_path, ref=branch)
                repo.update_file(
                    path=file_path,
                    message=f"Auto-update: {mensaje_commit}",
                    content=json_str,
                    sha=content.sha,
                    branch=branch
                )
            except GithubException as ex:
                if ex.status == 404:
                    repo.create_file(
                        path=file_path,
                        message=f"Crear archivo: {mensaje_commit}",
                        content=json_str,
                        branch=branch
                    )
                else:
                    raise ex
            return True
        except GithubException as e:
            if intento < retries - 1:
                time_lib.sleep(0.5)
            else:
                st.error(f"❌ Error al guardar en {file_path} tras varios intentos: {e}")
                return False

# ==========================================
# LÓGICA DE NEGOCIO Y PERSISTENCIA JSON
# ==========================================
def obtener_payload_predeterminado() -> dict:
    return {
        "ingresos": [],
        "modulos_estado": {"1": False},
        "solicitudes_acceso": []
    }

def obtener_datos_portal() -> dict:
    return leer_json_github(FILE_PORTAL_DATOS, obtener_payload_predeterminado())

def registrar_ingreso(nombre: str, canal: str):
    data = obtener_datos_portal()
    now = obtener_hora_colombia_str()
    
    nuevo_id = max([i.get("id", 0) for i in data["ingresos"]], default=0) + 1
    
    nuevo_registro = {
        "id": nuevo_id,
        "nombre": nombre.strip(),
        "canal": canal,
        "fecha_hora": now
    }
    
    data["ingresos"].insert(0, nuevo_registro)
    escribir_json_github(FILE_PORTAL_DATOS, data, f"Registro ingreso usuario {nombre}")

def obtener_historial_ingresos() -> pd.DataFrame:
    data = obtener_datos_portal()
    ingresos = data.get("ingresos", [])
    if not ingresos:
        return pd.DataFrame(columns=["ID", "Nombre", "Canal", "Fecha / Hora (COL)"])
    
    df = pd.DataFrame(ingresos)
    return df.rename(columns={
        "id": "ID",
        "nombre": "Nombre",
        "canal": "Canal",
        "fecha_hora": "Fecha / Hora (COL)"
    })

def eliminar_ingreso_por_id(ingreso_id: int):
    data = obtener_datos_portal()
    data["ingresos"] = [i for i in data["ingresos"] if i.get("id") != ingreso_id]
    escribir_json_github(FILE_PORTAL_DATOS, data, f"Eliminar ingreso ID {ingreso_id}")

def vaciar_todo_el_historial():
    data = obtener_datos_portal()
    data["ingresos"] = []
    escribir_json_github(FILE_PORTAL_DATOS, data, "Vaciar historial completo de ingresos")

def obtener_estado_modulos() -> dict:
    data = obtener_datos_portal()
    modulos = data.get("modulos_estado", {"1": False})
    return {int(k): bool(v) for k, v in modulos.items()}

def cambiar_estado_modulo(modulo_id: int, activo: bool):
    data = obtener_datos_portal()
    if "modulos_estado" not in data:
        data["modulos_estado"] = {}
    data["modulos_estado"][str(modulo_id)] = activo
    escribir_json_github(FILE_PORTAL_DATOS, data, f"Cambio estado modulo {modulo_id} a {activo}")

def solicitar_acceso_modulo(nombre: str, canal: str, session_token: str, ip: str, modulo_id: int):
    data = obtener_datos_portal()
    now = obtener_hora_colombia_str()
    solicitudes = data.get("solicitudes_acceso", [])
    
    # Eliminar solicitud previa existente para la misma sesión y módulo (INSERT OR REPLACE)
    solicitudes = [s for s in solicitudes if not (s.get("session_token") == session_token and s.get("modulo_id") == modulo_id)]
    
    nuevo_id = max([s.get("id", 0) for s in data.get("solicitudes_acceso", [])], default=0) + 1
    
    nueva_solicitud = {
        "id": nuevo_id,
        "nombre": nombre.strip(),
        "canal": canal,
        "session_token": session_token,
        "ip": ip,
        "modulo_id": modulo_id,
        "estado": "PENDIENTE",
        "fecha_solicitud": now
    }
    
    solicitudes.insert(0, nueva_solicitud)
    data["solicitudes_acceso"] = solicitudes
    escribir_json_github(FILE_PORTAL_DATOS, data, f"Solicitud acceso modulo {modulo_id} usuario {nombre}")

def obtener_estado_solicitud(session_token: str, modulo_id: int) -> str:
    data = obtener_datos_portal()
    solicitudes = data.get("solicitudes_acceso", [])
    sol = next((s for s in solicitudes if s.get("session_token") == session_token and s.get("modulo_id") == modulo_id), None)
    return sol.get("estado", "NO_SOLICITADO") if sol else "NO_SOLICITADO"

def obtener_todas_solicitudes() -> pd.DataFrame:
    data = obtener_datos_portal()
    solicitudes = data.get("solicitudes_acceso", [])
    if not solicitudes:
        return pd.DataFrame()
    return pd.DataFrame(solicitudes)

def actualizar_estado_solicitud(solicitud_id: int, nuevo_estado: str):
    data = obtener_datos_portal()
    for s in data.get("solicitudes_acceso", []):
        if s.get("id") == solicitud_id:
            s["estado"] = nuevo_estado
            break
    escribir_json_github(FILE_PORTAL_DATOS, data, f"Actualizar estado solicitud {solicitud_id} a {nuevo_estado}")

def eliminar_solicitud(solicitud_id: int):
    data = obtener_datos_portal()
    data["solicitudes_acceso"] = [s for s in data.get("solicitudes_acceso", []) if s.get("id") != solicitud_id]
    escribir_json_github(FILE_PORTAL_DATOS, data, f"Eliminar solicitud {solicitud_id}")

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
# DETECCIÓN Y VALIDACIÓN DE IP DESDE SECRETS
# ==========================================
def obtener_ip_cliente_javascript():
    """Ejecuta JS en el navegador para obtener la IP pública real del cliente."""
    js_code = "await fetch('https://api.ipify.org?format=json').then(r => r.json()).then(d => d.ip)"
    return st_javascript(js_code)

def validar_ip_tigo(ip_usuario: str) -> bool:
    """Valida si la IP detectada coincide con alguna de las IPs/subredes en secrets.toml."""
    if not ip_usuario or not isinstance(ip_usuario, str):
        return False
    
    rangos_permitidos = st.secrets.get("network", {}).get("ips_permitidas", ["127.0.0.1"])
    
    try:
        ip_obj = ipaddress.ip_address(ip_usuario.strip())
        for red_o_ip in rangos_permitidos:
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
# GESTIÓN DE SESIÓN
# ==========================================
if "user_authenticated" not in st.session_state:
    st.session_state.user_authenticated = False
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False
if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = {}

# ==========================================
# VERIFICACIÓN RIGUROSA DE IP (CORTAFUEGOS CLIENTE)
# ==========================================
ip_detectada = obtener_ip_cliente_javascript()

if ip_detectada is None or ip_detectada == 0:
    st.info("⏳ Validando conexión con la red corporativa...")
    st.stop()

if not validar_ip_tigo(str(ip_detectada)):
    st.error("🚫 **ACCESO NO AUTORIZADO**")
    st.warning(
        f"No puedes ingresar a este portal desde tu red actual.\n\n"
        f"**IP detectada:** `{ip_detectada}`\n\n"
        f"Por razones de seguridad, la plataforma solo está disponible desde la red corporativa autorizada (Tigo)."
    )
    st.stop()

# ==========================================
# INTERFAZ Y NAVEGACIÓN
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
                        solicitar_acceso_modulo(user['nombre'], user['canal'], st.session_state.session_token, str(ip_detectada), m['id'])
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
                    file_name=f"reporte_ingresos_{obtener_fecha_hora_colombia().strftime('%Y%m%d_%H%M')}.csv",
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
