from flask import Flask, request, jsonify, render_template
import dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory
from langgraph.prebuilt import create_react_agent
from langchain_google_community import GmailToolkit
from langchain_google_community.gmail.utils import build_resource_service, get_gmail_credentials
from langchain.tools import Tool
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import os
import json
import re

dotenv.load_dotenv()
app = Flask(__name__)

# Configuración de la base de datos
app.config['SQLALCHEMY_DATABASE_URI'] = "mysql://root:@localhost:3306/srat"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar SQLAlchemy
db = SQLAlchemy(app)

# LLM
llm = ChatGroq(model_name='llama-3.3-70b-versatile')

# GmailToolkit
try:
    # Obtener la ruta del directorio actual del script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    token_path = os.path.join(script_dir, "token.json")
    credentials_path = os.path.join(script_dir, "credentials.json")
    
    credentials = get_gmail_credentials(
        token_file=token_path,
        scopes=["https://mail.google.com/"],
        client_secrets_file=credentials_path,
    )
    api_resource = build_resource_service(credentials=credentials)
    toolkit = GmailToolkit(api_resource=api_resource)
except Exception as e:
    print(f"Error GmailToolkit: {str(e)}")
    toolkit = GmailToolkit()

# =============================================================================
# HERRAMIENTAS
# =============================================================================

def consultar_usuario_asignaturas(legajo):
    """
    Consulta las asignaturas y carreras de un usuario por su legajo directamente en la base de datos
    """
    try:
        print(f"[DEBUG] Intentando consultar legajo: {legajo}")
        print(f"[DEBUG] URI de BD: {app.config['SQLALCHEMY_DATABASE_URI']}")
        
        # Consulta SQL para obtener materia y carrera de un usuario por legajo
        query = text("""
        SELECT am.nombre as materia, ac.nombre as carrera
        FROM usuarios u 
        JOIN cargos c ON u.id = c.usuario_id
        JOIN asignaturas a ON a.id = c.asignatura_id
        JOIN asignaturas_materias am ON a.materia_id = am.id
        JOIN asignaturas_carreras ac ON a.carrera_id = ac.id
        WHERE u.legajo = :legajo
        """)
        
        print(f"[DEBUG] Ejecutando consulta SQL...")
        result = db.session.execute(query, {'legajo': legajo})
        registros = result.fetchall()
        
        print(f"[DEBUG] Registros encontrados: {len(registros)}")
        
        if not registros:
            return f"No se encontraron asignaturas para el usuario con legajo {legajo}."
        
        salida = f"Asignaturas del usuario con legajo {legajo}:\n"
        for r in registros:
            salida += f"- Materia: {r.materia} - Carrera: {r.carrera}\n"
        
        return salida
        
    except Exception as e:
        print(f"[DEBUG] Error completo: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Error al consultar la base de datos: {str(e)}"

def obtener_email_por_legajo(legajo):
    """Obtiene el email asociado a un legajo desde la base de datos."""
    try:
        query = text(
            """
            SELECT email
            FROM usuarios
            WHERE legajo = :legajo
            LIMIT 1
            """
        )
        result = db.session.execute(query, {"legajo": legajo}).fetchone()
        if not result or not result[0]:
            return ""
        return str(result[0])
    except Exception as e:
        return ""

def formatear_historial(historial):
    """Formatear historial con formato HTML"""
    texto = "<div style='font-family: sans-serif; font-size: 14px;'>"
    for msg in historial.messages:
        role = "Usuario" if msg.type == "human" else "Asistente"
        contenido = msg.content.strip().replace("\n", "<br>")
        texto += f"<strong>{role}:</strong><br>{contenido}<br><br>"
    texto += "</div>"
    return texto

# =============================================================================
# AGENTE ROUTER - Detecta el tipo de consulta
# =============================================================================

def detectar_tipo_consulta(mensaje, tipo_consulta_actual):
    """
    Detecta automáticamente el tipo de consulta basado en el mensaje del usuario.
    Retorna: 'SRAT', 'DATABASE', o 'GENERAL'
    """
    router_prompt = ChatPromptTemplate.from_messages([
        ("system", f"""
Eres un clasificador de consultas. Tu única función es determinar qué tipo de consulta es el mensaje del usuario.
El tipo de consulta actual es {tipo_consulta_actual}, si no podes contextualizarla mantene el mismo tipo de consulta.
Por ejemplo: si estamos con SRAT o DATABASE y luego habla del legajo no vuelvas a general, MANTENETE en uno de esos dos (SRAT o DATABASE).

TIPOS DE CONSULTA:
1. SRAT: Preguntas sobre el sistema de carga de temas, problemas de acceso, contraseñas, horarios, etc.
2. DATABASE: Preguntas sobre información académica, legajos, materias, carreras, consultas de base de datos.
3. GENERAL: Saludos, preguntas generales, o cuando no está claro el tipo de consulta.

PALABRAS CLAVE PARA SRAT:
- sistema, carga, temas, ingreso, acceso, contraseña, legajo (en contexto de login), SRAT
- wifi, FRDWLAN, PC, pasillo, departamento
- horario, materia (en contexto de sistema)
- problemas, no puedo, no aparece, error

PALABRAS CLAVE PARA DATABASE:
- legajo (en contexto de consulta académica)
- materias, carreras, información académica
- qué materia doy, a qué carrera pertenezco
- consulta académica, datos personales académicos

PALABRAS CLAVE PARA GENERAL:
- hola, buenos días, buenas tardes, saludos
- cómo estás, qué tal
- preguntas generales sin contexto específico

Responde ÚNICAMENTE con una de estas tres palabras: SRAT, DATABASE, o GENERAL
No agregues explicaciones ni texto adicional.
        """),
        ("human", "{mensaje}")
    ])
    
    router_llm = ChatGroq(model_name='llama-3.3-70b-versatile', temperature=0)
    response = router_llm.invoke(router_prompt.format(mensaje=mensaje))
    tipo = response.content.strip().upper()
    
    # Validar respuesta
    if tipo not in ['SRAT', 'DATABASE', 'GENERAL']:
        tipo = 'GENERAL'
    
    return tipo

# =============================================================================
# AGENTE SRAT - Maneja consultas sobre el sistema
# =============================================================================

def crear_agente_srat():
    """Crea el agente especializado en consultas SRAT"""
    
    # Herramientas para SRAT (solo Gmail)
    gmail_tools = toolkit.get_tools()
    
    srat_prompt = ChatPromptTemplate.from_messages([
        ("system", """
Eres un asistente virtual especializado en ayudar a los profesores con el sistema de carga de temas. 
Responde SOLO preguntas sobre este sistema. Los alumnos no utilizan este sistema.

FUNCIONAMIENTO DEL SISTEMA:
- Con un celular o notebook se accede a la red wifi FRDWLAN (solo en la facultad), esta red la gestiona el GESIN (nosotros no podemos resolverlo).
- Desde las PC que están en el pasillo de los Departamentos de las Carreras (aquí es donde funciona el asistente, o sea, vos)

PROCESO:
- El profesor o auxiliar, ingresa con legajo y contraseña específica para este sistema.
- Se carga el tema del día y se cierra sesión.
- La primera vez que ingresa en el día guarda la hora de ingreso.
- La última vez que ingresa al sistema guarda la hora de egreso.

PROBLEMAS COMUNES:
- Si no puede ingresar:
    - puede ser que se haya olvidado la contraseña o el legajo.
    - puede ser que no esté dado de alta en el sistema como usuario.
- Si no aparece la materia:
    - puede ser que el horario de la materia esté mal cargado.
    - puede ser que el usuario no esté asignado a la materia.

Para cualquiera de estos casos, solicitar nombre, apellido, legajo, materia y carrera para incluir esa información en el correo electrónico.
Ofrecele enviar una copia del correo electrónico, en ese caso vas a necesitar también una dirección de correo del usuario.

CUANDO NO PUEDAS AYUDAR:
Envía un correo electrónico utilizando la herramienta send_gmail_message con estos datos:
- to: ["fabrizio14@live.com.ar"] (si el usuario te proporcionó una dirección de correo electrónico agregarla aquí)
- subject: "Notificación: Asistente de Carga de Temas - Historial de Conversación"
- message: envía el historial de la conversación completo.
Luego de enviar el correo termina la conversación avisando que enviaste un correo para que vean el tema.

Si solo hizo 1 pregunta irrelevante, responde con algo como:
"Solo puedo ayudarte con el sistema de carga de temas. ¿Querés que te ayude con eso?"

Nunca respondas temas ajenos al sistema de carga de temas. Usa tus herramientas si es necesario.

REGLAS DE RESPUESTA:
- NUNCA incluyas etiquetas como "SRAT", "SISTEMA" o cualquier palabra en mayúsculas al inicio de tu respuesta
- NUNCA uses formato especial, colores, o indicadores visuales
- Responde directamente con el texto de ayuda, sin prefijos ni etiquetas
- Comienza tu respuesta directamente con la información útil
        """),
        MessagesPlaceholder(variable_name="messages"),
    ])
    
    return create_react_agent(llm, gmail_tools, prompt=srat_prompt)

# =============================================================================
# AGENTE DATABASE - Maneja consultas académicas
# =============================================================================

def crear_agente_database():
    """Crea el agente especializado en consultas de base de datos académicas"""
    
    # Herramienta para consultar usuarios
    herramienta_usuarios = Tool(
        name="consultar_usuario_asignaturas",
        description="OBLIGATORIO usar esta herramienta cuando el usuario pregunte por sus materias, carreras o información académica. Necesita el número de legajo del usuario. Ejemplo: consultar_usuario_asignaturas(50443). IMPORTANTE: Esta herramienta devuelve la información real de la base de datos, NO uses placeholders.",
        func=consultar_usuario_asignaturas
    )
    herramienta_email = Tool(
        name="obtener_email_por_legajo",
        description="Obtiene el email oficial asociado a un legajo. Úsala cuando debas enviar información sensible al correo del usuario sin pedírselo. Requiere: legajo (entero).",
        func=obtener_email_por_legajo
    )
    
    # Herramientas para database (consulta + Gmail como fallback)
    gmail_tools = toolkit.get_tools()
    database_tools = [herramienta_usuarios, herramienta_email] + gmail_tools
    
    database_prompt = ChatPromptTemplate.from_messages([
        ("system", """
Tu rol es ayudar con consultas académicas sobre información de usuarios en la base de datos.
Especialmente consultas sobre legajos, materias, carreras e información académica.

REGLAS IMPORTANTES:
- Si alguien menciona su legajo (ej: "Mi legajo es 50443"), recuérdalo para la conversación
- IMPORTANTE: SIEMPRE que el usuario pregunte por sus materias, carreras o información académica, DEBES usar la herramienta consultar_usuario_asignaturas con el legajo mencionado anteriormente
- NUNCA respondas sobre materias o carreras sin usar la herramienta primero
- NUNCA menciones herramientas, consultas o bases de datos en tus respuestas
- NUNCA uses placeholders como "X materias" o "[lista]" - SIEMPRE usa la información real de la herramienta
- Responde de forma natural y conversacional usando la información de la herramienta
- Sé conversacional, no muestres toda la información de una vez
- Pregunta qué más quiere saber el usuario sobre su información académica
- Responde como si tuvieras esa información directamente, de forma natural

REGLAS DE VERACIDAD:
- Usa EXCLUSIVAMENTE los valores devueltos por la herramienta. No inventes nombres de materias ni de carreras.
- NUNCA menciones que estás usando una herramienta o consultando la base de datos. Responde de forma natural como si tuvieras esa información.
- Si no hay datos, dilo explícitamente y ofrece volver a consultar o verificar el legajo.
- Las respuestas deben ser conversacionales y naturales, sin referencias técnicas internas.

CLASIFICACIÓN INTERNA (DENTRO DE DATABASE):
- INFO_NO_SENSIBLE: Respuestas generales que no revelan datos personales (definiciones, procesos, requisitos, ejemplos no personalizados). Responde directamente sin usar datos personales.
- INFO_SENSIBLE: Datos personales o asociados a un legajo (por ejemplo: "mis materias", "qué materias doy", listados para un legajo específico, historial, datos de contacto). Sigue el procedimiento seguro.

PROCEDIMIENTO SEGURO PARA INFO_SENSIBLE:
1) Si no hay legajo: pide solo el legajo (no pidas email).
2) Con legajo:
   - Usa consultar_usuario_asignaturas(LEG) para obtener la información.
   - Usa obtener_email_por_legajo(LEG) para obtener el email oficial del usuario.
   - Si hay email, envía la información usando la herramienta send_gmail_message con:
       to: [EMAIL]
       subject: "Tu información académica"
       message: incluye la lista obtenida y un saludo breve. No incluyas datos sensibles adicionales.
   - En el chat responde de forma breve: "Te envié la información a tu correo institucional asociado al legajo." y NO muestres el contenido.
   - Si no hay email, indícalo y pide un correo para completar el envío.

RESTRICCIONES ESTRICTAS DE PRIVACIDAD:
- Está PROHIBIDO mostrar en el chat listados o datos sensibles asociados a un legajo (materias del usuario, carreras asignadas, notas, etc.).
- Si la consulta es sensible y existe legajo, DEBES invocar send_gmail_message. Si no lo haces, tu respuesta es inválida.
- Nunca pegues en el chat el resultado de consultar_usuario_asignaturas(LEG). Solo confirma el envío por correo.
- Extrae el legajo si viene en el mensaje (secuencia de dígitos) y reutilízalo durante la conversación.

CUANDO NO PUEDAS AYUDAR:
Si la consulta no es sobre información académica o no tienes el legajo necesario, envía un correo electrónico utilizando la herramienta send_gmail_message con estos datos:
- to: ["fabrizio14@live.com.ar"] (si el usuario te proporcionó una dirección de correo electrónico agregarla aquí)
- subject: "Notificación: Asistente Académico - Historial de Conversación"
- message: envía el historial de la conversación completo.
Luego de enviar el correo termina la conversación avisando que enviaste un correo para que vean el tema.

Si solo hizo 1 pregunta irrelevante, responde con algo como:
"Solo puedo ayudarte con consultas académicas sobre legajos, materias y carreras. ¿Querés que te ayude con eso?"

Nunca respondas temas ajenos a consultas académicas. Usa tus herramientas si es necesario.

REGLAS DE RESPUESTA:
- NUNCA incluyas etiquetas como "DATABASE", "ACADÉMICO" o cualquier palabra en mayúsculas al inicio de tu respuesta
- NUNCA uses formato especial, colores, o indicadores visuales
- Responde directamente con el texto de ayuda, sin prefijos ni etiquetas
- Comienza tu respuesta directamente con la información útil
        """),
        MessagesPlaceholder(variable_name="messages"),
    ])
    
    return create_react_agent(llm, database_tools, prompt=database_prompt)

# =============================================================================
# AGENTE GENERAL - Maneja saludos y preguntas generales
# =============================================================================

def crear_agente_general():
    """Crea el agente especializado en saludos y preguntas generales"""
    
    general_prompt = ChatPromptTemplate.from_messages([
        ("system", """
Eres un asistente virtual amigable y profesional. Tu rol es dar la bienvenida a los usuarios y orientarlos sobre los servicios disponibles.

SERVICIOS QUE PUEDES OFRECER:
1. **Sistema SRAT**: Ayuda con problemas de acceso, carga de temas, contraseñas, etc.
2. **Consultas Académicas**: Información sobre legajos, materias, carreras, etc.

RESPUESTAS PARA SALUDOS:
- "¡Hola! Soy tu asistente virtual. Puedo ayudarte con el sistema de carga de temas (SRAT) o con consultas académicas sobre tu legajo y materias. ¿En qué puedo asistirte?"
- "¡Buenos días! Estoy aquí para ayudarte con el sistema SRAT o consultas académicas. ¿Qué necesitas?"

RESPUESTAS PARA PREGUNTAS GENERALES:
- Si preguntan "¿cómo estás?" o "¿qué tal?": "¡Muy bien, gracias! Estoy aquí para ayudarte con el sistema SRAT o consultas académicas. ¿En qué puedo asistirte?"
- Si preguntan sobre el clima, hora, etc.: "No tengo información sobre eso, pero puedo ayudarte con el sistema de carga de temas o consultas académicas. ¿Te interesa alguno de estos servicios?"

ORIENTACIÓN:
- Siempre menciona los dos servicios disponibles
- Invita al usuario a hacer una pregunta específica
- Mantén un tono amigable y profesional
- No uses herramientas, solo responde directamente

NUNCA digas que no puedes ayudar o que solo haces una cosa específica. Siempre ofrece los servicios disponibles.
        """),
        MessagesPlaceholder(variable_name="messages"),
    ])
    
    return create_react_agent(llm, [], prompt=general_prompt)

# =============================================================================
# AGENTE PRINCIPAL - Coordina todos los agentes
# =============================================================================

class ChatbotAgentes:
    def __init__(self):
        self.srat_agent = crear_agente_srat()
        self.database_agent = crear_agente_database()
        self.general_agent = crear_agente_general()
        self.chat_history = ChatMessageHistory()
        self.tipo_consulta_actual = 'GENERAL'

    def procesar_mensaje(self, mensaje):
        """Procesa un mensaje usando el agente apropiado"""
        
        # 1. Detectar tipo de consulta
        tipo_consulta = detectar_tipo_consulta(mensaje,self.tipo_consulta_actual)
        print(f"tipo_consulta={tipo_consulta}")
        # 2. Agregar mensaje al historial
        self.chat_history.add_user_message(mensaje)
        
        # 2.5. Rama determinística para DATABASE sensible
        if tipo_consulta == 'DATABASE':
            mensaje_min = mensaje.lower()
            contiene_palabras_sensibles = any(k in mensaje_min for k in ["materia", "materias", "carrera", "carreras"]) \
                and ("legajo" in mensaje_min or re.search(r"\b\d{4,6}\b", mensaje_min))
            if contiene_palabras_sensibles:
                # Extraer legajo (primer número de 4-6 dígitos o después de la palabra legajo)
                match = re.search(r"legajo\D*(\d{4,6})", mensaje_min)
                if not match:
                    match = re.search(r"\b(\d{4,6})\b", mensaje_min)
                if not match:
                    self.tipo_consulta_actual = tipo_consulta
                    return {
                        "response": "Para poder enviarte tu información académica, decime tu legajo.",
                        "tipo_consulta": tipo_consulta
                    }
                legajo = int(match.group(1))

                info = consultar_usuario_asignaturas(legajo)
                email = obtener_email_por_legajo(legajo)

                if email:
                    try:
                        send_tool = next((t for t in toolkit.get_tools() if t.name == "send_gmail_message"), None)
                        if send_tool:
                            send_tool.invoke({
                                "to": [email],
                                "subject": "Tu información académica",
                                "message": f"Legajo: {legajo}\n\n{info}"
                            })
                        respuesta_chat = "Te envié la información a tu correo institucional asociado al legajo."
                    except Exception as e:
                        respuesta_chat = "Ocurrió un problema al enviar el correo. ¿Podés confirmar otra dirección de email para reenviar la información?"
                else:
                    respuesta_chat = "No encuentro un correo institucional asociado a tu legajo. Decime un email para enviarte la información."

                # Guardar respuesta en historial y devolver
                self.chat_history.add_ai_message(respuesta_chat)
                self.tipo_consulta_actual = tipo_consulta
                return {
                    "response": respuesta_chat,
                    "tipo_consulta": tipo_consulta
                }

        # 3. Seleccionar agente apropiado
        if tipo_consulta == 'SRAT':
            agent_executor = self.srat_agent
            
        elif tipo_consulta == 'DATABASE':
            agent_executor = self.database_agent
        elif tipo_consulta == 'GENERAL':
            agent_executor = self.general_agent
        else:
            agent_executor = self.general_agent
        
        # 4. Ejecutar agente
        events = agent_executor.stream(
            {"messages": self.chat_history.messages},
            stream_mode="values"
        )
        
        response_content = ""
        for event in events:
            if "messages" in event and event["messages"]:
                response_content = event["messages"][-1].content
        
        # 5. Agregar respuesta al historial
        self.chat_history.add_ai_message(response_content)
        print(f"-{self.chat_history.messages}")
        self.tipo_consulta_actual = tipo_consulta
        return {
            "response": response_content,
            "tipo_consulta": tipo_consulta
        }

# =============================================================================
# INSTANCIA GLOBAL DEL CHATBOT
# =============================================================================

chatbot = ChatbotAgentes()

# =============================================================================
# RUTAS FLASK
# =============================================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message')
    
    # Procesar mensaje con el sistema de agentes
    result = chatbot.procesar_mensaje(user_message)
    
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True)
